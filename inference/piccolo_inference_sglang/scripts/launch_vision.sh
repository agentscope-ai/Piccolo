#!/usr/bin/env bash
set -euo pipefail
if (( $# < 3 )); then
  echo "Usage: $0 MODEL_PATH GPU PORT [additional SGLang arguments...]" >&2
  exit 2
fi
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
MODEL_PATH=$1
GPU=$2
PORT=$3
shift 3
PYTHON=${PYTHON:-python3}
export PYTHONDONTWRITEBYTECODE=1
export SGLANG_PLUGINS=piccolo
export CUDA_VISIBLE_DEVICES="$GPU"
export PICCOLO_OCR_ENABLED="${PICCOLO_OCR_ENABLED:-0}"
export PICCOLO_OCR_PYTHON="${PICCOLO_OCR_PYTHON:-$PYTHON}"
export PICCOLO_OCR_DEVICE="${PICCOLO_OCR_DEVICE:-gpu:0}"
if [[ "$PICCOLO_OCR_ENABLED" == 1 ]]; then
  : "${PICCOLO_OCR_MODEL_DIR:?Set PICCOLO_OCR_MODEL_DIR to the verified OCR model directory}"
  export PICCOLO_OCR_MODEL_DIR
fi
export HF_HUB_OFFLINE=1
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=8
export XDG_CACHE_HOME="$ROOT/.cache"
export TRITON_CACHE_DIR="$XDG_CACHE_HOME/vision/triton"
export TORCH_EXTENSIONS_DIR="$XDG_CACHE_HOME/vision/torch_extensions"
exec "$PYTHON" -m sglang.launch_server \
  --model-path "$MODEL_PATH" --tokenizer-path "$MODEL_PATH" \
  --served-model-name "${SERVED_MODEL_NAME:-Piccolo}" \
  --host 0.0.0.0 --port "$PORT" --api-key EMPTY \
  --tp-size 1 --dtype bfloat16 --context-length 32768 --max-total-tokens 32768 \
  --mem-fraction-static "${MEM_FRACTION_STATIC:-0.80}" \
  --json-model-override-args '{"text_config":{"is_causal":false}}' \
  --attention-backend fa3 --disable-radix-cache --chunked-prefill-size -1 \
  --disable-custom-all-reduce --max-running-requests 1 --disable-cuda-graph \
  --mamba-radix-cache-strategy extra_buffer_lazy --mamba-full-memory-ratio 0.4 \
  --kv-cache-dtype auto --mamba-ssm-dtype float32 \
  --mm-process-config '{"image":{"min_pixels":65536,"max_pixels":1638400}}' \
  --mm-preprocess-cache-size-mb 0 "$@"
