# Piccolo inference on SGLang

A native SGLang plugin providing `/v1/systemone` for text and `/v1/decisions` for vision. Both routes call the tokenizer manager in the same process, preserving native API key authentication and the `/generate`, `/health`, and `/server_info` endpoints.

| API | Input format | Launch script defaults |
|---|---|---|
| `/v1/systemone` | Flex header, flex_twice, 3,000-token reread threshold | FP8, TP1, 64K context |
| `/v1/decisions` | Question list → body → images in their original order → repeated body (version 20261030) | BF16, TP1, 32K context |

## Installation

Run from the repository root:

```bash
cd inference/piccolo_inference_sglang
```

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

The default installation includes only the main inference dependencies. OCR is optional and disabled by default; it requires the `ocr` extra and `PICCOLO_OCR_ENABLED=1`.

### Optional OCR setup

Install the `ocr` extra into the same `.venv` created above:

```bash
uv pip install --python .venv/bin/python --prerelease=allow '.[ocr]' \
  --extra-index-url https://www.paddlepaddle.org.cn/packages/stable/cu126/ \
  --index-strategy unsafe-best-match
```

Prepare the OCR weights:

```bash
uv run --no-sync python -m piccolo_inference_sglang.prepare_ocr_models \
  --out "$PWD/ocr_models"
```

## Start the API server

Download the checkpoint with `hf download agentscope-ai/Piccolo-4B --local-dir /models/Piccolo-4B`.

Run on a Linux GPU node, passing the checkpoint path, an available GPU index or UUID, and the API port, in that order. Additional native SGLang arguments can be appended:

```bash
# for decision-index text
bash scripts/launch_sglang.sh /models/Piccolo-4B 0 18604
# for decision-index vision
bash scripts/launch_vision.sh /models/Piccolo-4B 0 18704
```

The served model name defaults to `Piccolo`, independently of the checkpoint directory name; set `SERVED_MODEL_NAME` to override it.

Query the effective configuration from the evaluation machine:

```bash
curl -fsS http://model-host:18704/health -H 'Authorization: Bearer EMPTY'
curl -fsS http://model-host:18704/server_info -H 'Authorization: Bearer EMPTY'
```

### Enable OCR for vision (Optional)

The vision command above runs without OCR. To enable it, restart the vision service with:

```bash
PICCOLO_OCR_ENABLED=1 \
PICCOLO_OCR_PYTHON="$PWD/.venv/bin/python" \
PICCOLO_OCR_MODEL_DIR="$PWD/ocr_models" \
PYTHON="$PWD/.venv/bin/python" \
  bash scripts/launch_vision.sh /models/piccolo-4B-1028 0 18704
```

Check that ocr.enabled and ocr.ready are both true:

```bash
curl -fsS http://model-host:18704/v1/decisions/runtime -H 'Authorization: Bearer EMPTY'
```

OCR runs in a single worker, sharing the main model's GPU by default. It uses PP-OCRv5_mobile_det and en_PP-OCRv5_mobile_rec, with a detection side limit of 960 and recognition batch size 8.

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
  --model Piccolo \
  --option base_url=http://model-host:18704 \
  --workers 1 --chunk 1 \
  --out "$RESULT_DIR" \
  > "$LOG_DIR/piccolo-4B-1028.log" 2>&1 < /dev/null &
```

> The engine accepts services with OCR disabled by default. For an OCR evaluation, enable OCR on the server and add `--option require_ocr=true` to the command above.

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
  --option model=Piccolo \
  --out "$RESULT_DIR" \
  > "$LOG_DIR/piccolo-4B-1028.log" 2>&1 < /dev/null &
```

## Third-party notices

FlexDM prompt layout and Decision Index image resizing retain their MIT notices in [the bundled licenses](piccolo_inference_sglang/licenses/).
