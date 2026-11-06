# Evaluation

| Model | HarnessJevBench Hard ↑ | DataJevBench ↑ | JevBench Public ↑ | Decision Index Public ↑ |
| --- | ---: | ---: | ---: | ---: |
| Piccolo-27B | 84.41% | 82.60% | 92.21% | 68.59 |
| Piccolo-9B | 68.81% | 69.40% | 89.61% | 60.86 |
| Piccolo-4B | 62.03% | 70.60% | 87.01% | 58.00 |

[Results JSON](results.json) · [Live leaderboard](https://decisionplayground.agentscope.io/)

## Reproduce in one command

Start a [Piccolo decision server](../inference/sglang/README.md), then run from the repository root with Python 3.12 and Git:

```bash
python evaluation/reproduce.py --base-url http://127.0.0.1:18604 --model Piccolo-4B
```

The launcher fetches the pinned official benchmark sources, sends native `state` and `questions` to `/v1/systemone`, and runs each benchmark's official scorer. Results are written to a new directory under `var/evaluation/`; existing results are preserved. Use `--output PATH` to choose the directory.

| Benchmark | Source | Scope |
| --- | --- | --- |
| HarnessJevBench | [Official evaluator](https://github.com/agentscope-ai/HarnessJevBench) | Hard decisions and Soft probability distributions |
| DataJevBench | [Official evaluator](https://github.com/datajuicer/DataJevBench) | 500 data-workflow questions |
| JevBench | [Official evaluator](https://github.com/fstandhartinger/jevbench) | 231 original, easy and hard public tasks |
| Decision Index | [Official reproduction kit](https://github.com/apolinario/decision-index) | Public text suite |

Decision Index installs its reproduction dependencies and rebuilds the suite on first use. Accept the upstream dataset terms and authenticate with Hugging Face before rebuilding datasets that require access. To reuse a prepared suite, add `--decision-suite /path/to/suite`.

For a short integration check:

```bash
python evaluation/reproduce.py --base-url http://127.0.0.1:18604 --model Piccolo-4B \
  --benchmarks harness data jevbench --limit 2
```

- `--dry-run` writes the command plan without downloads or model calls.
- `--prepare-only` downloads the evaluators and prepares dependencies without inference.
- `--key-env PICCOLO_API_KEY` reads authentication from that environment variable when set.
- `--model-revision`, `--backend-revision` and `--hardware` record the local deployment in the run metadata.

[benchmarks.json](benchmarks.json) pins source revisions. Per-question outputs are generated locally by the evaluator. The repository distributes aggregate results and reproduction code.

## Local inference measurements

BF16, Q8_0 and Q4_K_M conversion checks are documented in their model cards. Each size's Q4_K_M regression covers 265 requests and 556 decisions across tool review, context retention and scoring. See the [QwenPaw measurements](../docs/QWENPAW.md#macos-本地延迟) for local latency and context compaction.
