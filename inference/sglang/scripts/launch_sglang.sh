#!/usr/bin/env bash
set -euo pipefail
if (( $# < 3 )); then
  echo "Usage: $0 MODEL_PATH GPU PORT [additional SGLang arguments...]" >&2
  exit 2
fi
MODEL_PATH=$1
GPU=$2
PORT=$3
shift 3
export SGLANG_PLUGINS=piccolo
export CUDA_VISIBLE_DEVICES="$GPU"
export TOKENIZERS_PARALLELISM=false
exec "${PYTHON:-python3}" -m sglang.launch_server \
  --model-path "$MODEL_PATH" --served-model-name "$(basename -- "$MODEL_PATH")" \
  --host "${HOST:-127.0.0.1}" --port "$PORT" --tp-size 1 \
  --trust-remote-code --dtype bfloat16 --context-length "${CONTEXT_LENGTH:-32768}" \
  --mem-fraction-static "${MEM_FRACTION_STATIC:-0.80}" \
  --mamba-ssm-dtype float32 "$@"
