"""Portable single-GPU SGLang entry point for all five archived Piccolo sizes."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True, help='Local HF checkpoint directory')
    p.add_argument('--size', required=True, choices=['0.8B', '2B', '4B', '9B', '27B'])
    p.add_argument('--gpu', default='0')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8000)
    p.add_argument('--served-model-name', default='Piccolo')
    p.add_argument('--ocr-model-dir', required=True)
    p.add_argument('--ocr-python', default=sys.executable)
    p.add_argument('--memory-fraction', type=float, default=0.75)
    p.add_argument('--context-length', type=int, default=32768)
    p.add_argument('--attention-backend', choices=['auto', 'fa3', 'triton'], default='auto')
    p.add_argument('--dry-run', action='store_true', help='Print launch without loading a model')
    a = p.parse_args()
    if ',' in a.gpu:
        raise ValueError('This release supports exactly one GPU per server')
    model = Path(a.model).expanduser().resolve()
    config = json.loads((model / 'config.json').read_text())
    profile_path = Path(__file__).with_name('profiles') / f'Piccolo-{a.size}.json'
    profile = json.loads(profile_path.read_text())
    language = profile['recipe']
    depth = config['text_config']['num_hidden_layers']
    if depth + sum(e-s for s,e in language['blocks'])*(len(language['per_block_pass_alphas'])-1) != language['language_layer_calls']:
        raise ValueError('Profile does not match checkpoint depth')
    if not 0 < a.memory_fraction < 1 or a.context_length < 1:
        raise ValueError('Invalid memory fraction or context length')
    root = Path(tempfile.mkdtemp(prefix='piccolo-sglang-'))
    loop = root/'language.json'
    loop.write_text(json.dumps(dict(blocks=language['blocks'], weights=language['per_block_pass_alphas'])))
    os.environ.update(CUDA_VISIBLE_DEVICES=a.gpu, SGLANG_PLUGINS='piccolo',
        PICCOLO_LOOP_PROFILE=str(profile_path), PICCOLO_CHECKPOINT=str(model),
        V35_LOOP_CONFIG=str(loop), PYTHONDONTWRITEBYTECODE='1',
        SGLANG_VIT_ENABLE_CUDA_GRAPH='0', PICCOLO_OCR_ENABLED='1',
        PICCOLO_OCR_WORKERS='1', PICCOLO_OCR_CPU_THREADS='2',
        PICCOLO_OCR_MODEL_DIR=str(Path(a.ocr_model_dir).resolve()),
        PICCOLO_OCR_PYTHON=a.ocr_python, PICCOLO_OCR_DEVICE='gpu:0',
        PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True',
        FLAGS_allocator_strategy='auto_growth', FLAGS_initial_gpu_memory_in_mb='256',
        FLAGS_reallocate_gpu_memory_in_mb='256',
        HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    os.environ['V35_SGLANG_MATERIALIZE_EACH_LAYER'] = '0' if a.size == '27B' else '1'
    os.environ.setdefault('OMP_NUM_THREADS', '8')
    backend = a.attention_backend
    if backend == 'auto':
        if a.dry_run:
            backend = 'AUTO_BY_DEVICE_CAPABILITY'
        else:
            import torch
            capability = torch.cuda.get_device_capability(0)
            backend = 'fa3' if capability[0] == 9 else 'triton'
    command = [sys.executable, '-m', 'sglang.launch_server',
        '--model-path', str(model), '--tokenizer-path', str(model),
        '--served-model-name', a.served_model_name, '--host', a.host, '--port', str(a.port),
        '--api-key', os.environ.get('DECISION_INDEX_API_KEY', 'EMPTY'),
        '--tp-size', '1', '--dtype', 'bfloat16',
        '--context-length', str(a.context_length), '--max-total-tokens', str(a.context_length),
        '--mem-fraction-static', str(a.memory_fraction),
        '--json-model-override-args', '{"text_config":{"is_causal":false}}',
        '--attention-backend', backend, '--disable-radix-cache', '--chunked-prefill-size', '-1',
        '--disable-custom-all-reduce', '--max-running-requests', '1',
        '--disable-cuda-graph', '--skip-server-warmup', '--mamba-radix-cache-strategy', 'extra_buffer_lazy',
        '--mamba-full-memory-ratio', '0.4', '--kv-cache-dtype', 'auto', '--mamba-ssm-dtype', 'float32',
        '--mm-process-config', '{"image":{"min_pixels":65536,"max_pixels":1638400}}',
        '--mm-preprocess-cache-size-mb', '0', '--enable-deterministic-inference']
    if a.dry_run:
        display_command = command.copy()
        credential_index = display_command.index('--api-key') + 1
        if display_command[credential_index] not in ('', 'EMPTY'):
            display_command[credential_index] = '<redacted>'
        print(json.dumps(dict(command=display_command, profile=profile, environment={key: os.environ[key] for key in [
            'CUDA_VISIBLE_DEVICES', 'SGLANG_PLUGINS', 'PICCOLO_LOOP_PROFILE',
            'PICCOLO_OCR_ENABLED', 'PICCOLO_OCR_DEVICE', 'PICCOLO_OCR_WORKERS',
            'V35_SGLANG_MATERIALIZE_EACH_LAYER']}), indent=2))
        return
    os.execv(sys.executable, command)


if __name__ == '__main__':
    main()
