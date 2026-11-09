#!/usr/bin/env bash
set -euo pipefail
if (( $# < 3 )); then
  echo "Usage: $0 MODEL_PATH GPU PORT [--input-profile flexdm|u03|single-pass] [additional SGLang arguments...]" >&2
  exit 2
fi
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
MODEL_PATH=$1
GPU=$2
PORT=$3
shift 3
# These are plugin options, not native SGLang arguments. Keep all other args intact.
INPUT_PROFILE=${PICCOLO_INPUT_PROFILE:-flexdm}
SGLANG_ARGS=()
while (( $# )); do
  case "$1" in
    --input-profile)
      if (( $# < 2 )); then echo "--input-profile requires a value" >&2; exit 2; fi
      INPUT_PROFILE=$2; shift 2 ;;
    --input-profile=*) INPUT_PROFILE=${1#*=}; shift ;;
    *) SGLANG_ARGS+=("$1"); shift ;;
  esac
done
case "$INPUT_PROFILE" in
  flexdm|u03|single-pass) ;;
  *) echo "Unknown input profile: $INPUT_PROFILE (expected flexdm, u03, single-pass)" >&2; exit 2 ;;
esac
export PICCOLO_INPUT_PROFILE="$INPUT_PROFILE"
PYTHON=${PYTHON:-python3}
export PYTHONDONTWRITEBYTECODE=1
export SGLANG_PLUGINS=piccolo
export CUDA_VISIBLE_DEVICES="$GPU"
export HF_HUB_OFFLINE=1
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-${HOME}/.cache/piccolo}"
export TRITON_CACHE_DIR="${TRITON_CACHE_DIR:-$XDG_CACHE_HOME/triton}"
export TORCH_EXTENSIONS_DIR="${TORCH_EXTENSIONS_DIR:-$XDG_CACHE_HOME/torch_extensions}"
exec "$PYTHON" -m sglang.launch_server \
  --model-path "$MODEL_PATH" --tokenizer-path "$MODEL_PATH" \
  --served-model-name "${SERVED_MODEL_NAME:-Piccolo}" \
  --host 0.0.0.0 --port "$PORT" --api-key EMPTY \
  --tp-size 1 --random-seed 42 --trust-remote-code --context-length 65536 \
  --quantization fp8 --mem-fraction-static "${MEM_FRACTION_STATIC:-0.85}" \
  --json-model-override-args '{"text_config":{"is_causal":false}}' \
  --attention-backend fa3 --disable-radix-cache --chunked-prefill-size -1 \
  --disable-custom-all-reduce --cuda-graph-max-bs-decode 32 \
  --mamba-full-memory-ratio 0.4 --kv-cache-dtype auto --mamba-ssm-dtype float32 \
  --mamba-radix-cache-strategy extra_buffer_lazy --skip-server-warmup "${SGLANG_ARGS[@]}"
