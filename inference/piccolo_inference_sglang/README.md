# Piccolo inference on SGLang

A native SGLang plugin providing `/v1/systemone` for text and `/v1/decisions` for vision. Both routes call the tokenizer manager in the same process, preserving native API key authentication and the `/generate`, `/health`, and `/server_info` endpoints.

| API | Input format | Launch script defaults |
|---|---|---|
| `/v1/systemone` | Flex header, flex_twice, 3,000-token reread threshold | FP8, TP1, 64K context |
| `/v1/decisions` | Question list → body → images in their original order → repeated body (version 20261030) | BF16, TP1, 32K context |

## Installation

Using pip:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --pre .
```

Or using [uv](https://docs.astral.sh/uv/):

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install --prerelease=allow .
```

## Start the API server

Run on a Linux GPU node, passing the checkpoint path, an available GPU index or UUID, and the API port, in that order. Additional native SGLang arguments can be appended:

```bash
bash scripts/launch_sglang.sh /models/piccolo-4B-1028 0 18604
bash scripts/launch_vision.sh /models/piccolo-4B-1028 1 18704 \
  --dist-init-addr 127.0.0.1:32104
```

Both scripts use TP1 and bidirectional full attention, while DeltaNet retains the backend’s causal computation. Radix caching and chunked prefill are disabled. The KV cache uses the default precision, and Mamba states use FP32. Query the effective configuration from the evaluation machine:

```bash
curl -fsS http://model-host:18704/health -H 'Authorization: Bearer EMPTY'
curl -fsS http://model-host:18704/server_info -H 'Authorization: Bearer EMPTY'
```

## Official vision evaluation

```bash
PLUGIN_ROOT=/path/to/piccolo_inference_sglang
DI_CODE=/path/to/decision-index
DI_SUITE=/path/to/work/vision
RESULT_DIR=/path/to/results/vision-bf16/piccolo-4B-1028
LOG_DIR=/path/to/logs/vision-bf16

export PYTHONPATH="$DI_CODE:$PLUGIN_ROOT"
export PYTHONDONTWRITEBYTECODE=1
export DECISION_INDEX_API_KEY=EMPTY
mkdir -p "$LOG_DIR"
cd "$DI_CODE"

nohup python -u -m decision_index vision pipeline \
  --dir "$DI_SUITE" \
  --engine piccolo_inference_sglang.decision_index_engine:VisionEngine \
  --model piccolo-4B-1028 \
  --option base_url=http://model-host:18704 \
  --workers 1 --chunk 1 \
  --out "$RESULT_DIR" \
  > "$LOG_DIR/piccolo-4B-1028.log" 2>&1 < /dev/null &
```

## Official text evaluation

Text evaluation uses the official HTTP engine:

```bash
DI_CODE=/path/to/decision-index
DI_SUITE=/path/to/suite-0.3
RESULT_DIR=/path/to/results/text-fp8/piccolo-4B-1028
LOG_DIR=/path/to/logs/text-fp8

export PYTHONPATH="$DI_CODE"
export PYTHONDONTWRITEBYTECODE=1
export DECISION_INDEX_API_KEY=EMPTY
mkdir -p "$LOG_DIR"
cd "$DI_CODE"

nohup python -u -m decision_index pipeline \
  --edition 0.3 --suite-dir "$DI_SUITE" \
  --engine http \
  --option base_url=http://model-host:18604 \
  --option model=piccolo-4B-1028 \
  --out "$RESULT_DIR" \
  > "$LOG_DIR/piccolo-4B-1028.log" 2>&1 < /dev/null &
```