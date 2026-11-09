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
python -m pip install --pre '.[inference]'
```

Or using [uv](https://docs.astral.sh/uv/):

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install --prerelease=allow '.[inference]'
```

Install `.[inference]` for the model server; installing `.` alone installs only the package. OCR is optional and disabled by default.

### Optional OCR setup

Install `.[ocr]` in a separate environment to keep Paddle's CUDA libraries separate from PyTorch's. Keep the `inference` and `ocr` extras in their respective environments:

```bash
uv venv --python 3.12 .venv-ocr
uv pip install --python .venv-ocr/bin/python --prerelease=allow '.[ocr]' \
  --extra-index-url https://www.paddlepaddle.org.cn/packages/stable/cu126/ \
  --index-strategy unsafe-best-match
```

Prepare the OCR weights using the OCR environment:

```bash
.venv-ocr/bin/python -m piccolo_inference_sglang.prepare_ocr_models \
  --out "$PWD/ocr_models"
```

## Start the API server

Run on a Linux GPU node, passing the checkpoint path, an available GPU index or UUID, and the API port, in that order. Additional native SGLang arguments can be appended:

```bash
# for decision-index text
bash scripts/launch_sglang.sh /models/piccolo-4B-1028 0 18604
# for decision-index vision
bash scripts/launch_vision.sh /models/piccolo-4B-1028 0 18704
```

The served model name defaults to `Piccolo`, independently of the checkpoint directory name; set `SERVED_MODEL_NAME` to override it.

### Optional text input profiles

The text service defaults to the original `flexdm` input format. Select a profile at startup:

```bash
bash scripts/launch_sglang.sh /models/piccolo-4B-1028 0 18604 --input-profile u03
# Other choices: --input-profile flexdm or --input-profile single-pass
```

| Profile | Input arrangement | Reread threshold (single-pass tokens of the complete request) |
|---|---|---|
| `flexdm` (default) | Question list first; repeat the body within the threshold | 3,000 |
| `u03` | Same layout; extend rereading for single-question requests | 12,000 for one question; 3,000 for multiple questions |
| `single-pass` | Question list first; body once | No rereading |

`PICCOLO_INPUT_PROFILE` is also supported; the command-line option takes precedence. `--input-profile=u03` is equivalent. Other arguments pass through to SGLang. When launching SGLang directly, set `PICCOLO_INPUT_PROFILE` and `SGLANG_PLUGINS=piccolo`; `--input-profile` belongs to our shell launcher, not the native SGLang CLI. Do not enable the older separate U03 plugin at the same time.

The profile is fixed for the service and cannot be overridden by an HTTP request. Apply the threshold to the complete question map before splitting subquestions. If repetition would exceed the context limit, the whole request falls back to single-pass input; if that still exceeds the limit, reject it without truncating. The text compiler reserves one answer token and accepts at most 65,535 input tokens per model row.

These profiles only change text input arrangement. Model weights, attention, candidate-logprob readout, precision and vision/OCR processing are unchanged. `single-pass` still includes the question list; it is not a raw chat template. U03 does not select BF16: the text launch script remains FP8. The response records the profile and revision under `evaluation_trace.flex`.

Text launcher caches default to the user's cache directory. Override `XDG_CACHE_HOME`, `TRITON_CACHE_DIR` and `TORCH_EXTENSIONS_DIR` as needed; keep runtime logs and evaluation outputs outside this repository.


Query the effective configuration from the evaluation machine:

```bash
curl -fsS http://model-host:18704/health -H 'Authorization: Bearer EMPTY'
curl -fsS http://model-host:18704/server_info -H 'Authorization: Bearer EMPTY'
```

### Enable OCR for vision (Optional)

The vision command above runs without OCR. To enable it, restart the vision service with:

```bash
PICCOLO_OCR_ENABLED=1 \
PICCOLO_OCR_PYTHON="$PWD/.venv-ocr/bin/python" \
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

## Validation and source packaging

Run the CPU contract tests in the installed environment:

```bash
python -m unittest discover -s tests -v
```

For a running text service, use the official Decision-Index HTTP engine and validator. Run from this repository with a Python environment that can import the official evaluation kit:

```bash
DI_CODE=/path/to/decision-index
export PYTHONPATH="$DI_CODE${PYTHONPATH:+:$PYTHONPATH}"
export DECISION_INDEX_API_KEY=EMPTY
python tests/http_text_smoke.py \
  --base-url http://model-host:18604 --model Piccolo \
  --expect-profile u03 --out /path/outside/source/text-smoke.json
```

Set `--expect-profile` to match the running service (`flexdm` if using the default). This checks real choice/noul requests, multiple subquestions and long input. The Jev `score` extension is separate from the official DI choice/noul contract. A smoke-test accuracy is not an official Decision-Index score.

For an OCR-enabled vision service, run the separate `tests/http_gpu_smoke.py` check with `--base-url`, `--model` and an external `--out` path. Text validation does not establish OCR GPU compatibility.

For submission, use the complete official pipelines above without `--limit`, `--rows` or `--no-verify`. Preserve `results.jsonl`, `status.json`, `environment.json` and the official summary/score artifacts; verify completion, denominators and error/unsupported counts. Declare immutable model/code revisions, input profile/revision, precision, attention, hardware/concurrency and any OCR models. Use one fixed input policy, never benchmark-specific prompts or answer caches; do not truncate inputs or drop candidates. Report end-to-end request latency including preprocessing and OCR when enabled.

`python scripts/build_submission.py` builds a source archive under `dist/`. To keep generated artifacts outside the development checkout, run it from a clean exported copy. The archive excludes environments, weights and runtime outputs; retain the upstream license notices in `piccolo_inference_sglang/licenses/` alongside the vendored code. Publishing and full-suite evaluation are separate steps, not performed by the build script.
