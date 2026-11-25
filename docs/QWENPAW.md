# Piccolo: Local Decision Models in QwenPaw

Piccolo reuses QwenPaw's GGUF downloader and llama.cpp management, along with Jev's existing decision model selection, automatic review, and context compaction controls. Complete weights, BF16, Q8_0, and Q4_K_M are published on [Hugging Face](MODELS.md). No additional Skill, cloud API key, or separate Jev service URL is required.

## Install QwenPaw and the runtime

Local Piccolo decision model integration was merged into QwenPaw main through **[PR #8463](https://github.com/agentscope-ai/QwenPaw/pull/8463)**. Get the official source and follow the repository's development installation instructions to set up QwenPaw:

```bash
git clone --branch main https://github.com/agentscope-ai/QwenPaw.git QwenPaw-Piccolo
cd QwenPaw-Piccolo
```

Then build the compatible llama.cpp runtime using the official **[runtime build and installation instructions](https://github.com/agentscope-ai/QwenPaw/blob/main/docs/local-piccolo.md#compatible-runtime)**. The guide pins upstream commit `f4d8af608a6b39946406f9439edfb6e83ca6a923` and applies the repository's `docs/patches/piccolo-llama.cpp.patch`. Stop the local model, back up the existing runtime, and install the new `llama-server` and matching shared libraries into the QwenPaw runtime directory printed by the guide.

Unmodified upstream binaries and standard Ollama chat interfaces do not implement the Piccolo protocol. Reinstalling an unmodified runtime removes support. Installing the runtime does not require changing the user's existing approval or compaction settings.

## Download and start

1. Open **Models → QwenPaw Local → Decision Models** and download a BF16 or Q8_0 model suitable for your device. If the entry is missing, select Hugging Face in custom downloads and enter a repository ID such as `agentscope-ai/Piccolo-4B-BF16`, `agentscope-ai/Piccolo-9B-Q8_0`, or `agentscope-ai/Piccolo-27B-Q4_K_M`.
2. The downloader fetches the GGUF files and instructions needed for inference, including all standard shards. Safetensors repositories without a suffix are for reference inference with complete checkpoints.
3. Once downloaded, click **Start**, then confirm the selection under **Models → Default Models → Decision Model**. Agent-specific settings can override the global default.

For standalone downloads, use the `AgentScope/Piccolo-*` repositories in the [ModelScope collection](https://www.modelscope.cn/collections/AgentScope/QwenPaw-Flash). QwenPaw currently identifies local decision models by `agentscope-ai/Piccolo-*`; select Hugging Face and the corresponding repository ID for custom downloads.

The catalog recommends BF16 and Q8_0 based on device memory:

| Size | Q8_0 recommendation threshold | BF16 recommendation threshold | BF16 download size |
| --- | ---: | ---: | ---: |
| 4B | 16 GB | 24 GB | 8.42 GB |
| 9B | 24 GB | 32 GB | 17.92 GB |
| 27B | 48 GB | 80 GB | 53.81 GB |

These are catalog display thresholds, not measured peak-memory guarantees. Q4_K_M has passed expanded numerical regression checks and is published for download by repository ID; see each model card for errors and limitations. The built-in llama.cpp runtime **manages one running model at a time**. Starting Piccolo replaces the local chat model in the same instance; conversations can use other providers.

## Use Jev's existing activation controls

- **Automatic review:** Enable **Use Decision Model** in the advanced options of the conversation's model menu, and set tool approval to **Decision Model Mode**. The agent's default mode is under **Runtime Configuration → Execution → Tool Approval Mode**.
- **Context compaction:** Enable context compaction under **Runtime Configuration → Context Capacity**, then expand **Decision Model Compaction** and enable its separate switch.

The model list only handles downloading, starting, stopping, and deleting models. Starting Piccolo does not automatically enable either feature. The [three-step setup screenshots](../assets/qwenpaw/README.md) show these controls.

## Local inference protocol

```text
Hugging Face GGUF → QwenPaw-managed llama.cpp
                 → /v1/systemone candidate-token scoring
                 → AgentScope Jev → automatic review / ReMe compaction
```

The protocol uses the `flex_twice` layout, reads logits for single-token candidate labels after `Answer: (`, and normalizes over the candidate set at temperature 1. This is equivalent to renormalizing the candidate tokens' log probabilities. It generates neither answer text nor probability JSON. Full-attention layers use bidirectional prompt attention; linear-attention layers retain their original computation.

Each question uses the complete prompt, with prefix caching and context shifting disabled and matching context/batch/microbatch sizes. The current QwenPaw implementation supports at most 8,192 tokens, including the repeated layout. Requests exceeding the budget fail explicitly and use the existing fallback rather than silently truncating. The original checkpoint's configured limit is separate from this runtime budget.

Native approval thresholds, manual-confirmation fallback, and context recovery remain in effect. Candidate probabilities are not a task-calibrated safety guarantee. See [inference documentation](../inference/README.md) for the reference implementation and minimal requests, and individual model cards for conversion and quantization evidence.

## Local latency on macOS

On a Mac with an M4 Pro and 24 GB of unified memory, three 4B GGUF formats were loaded separately using the same Piccolo llama.cpp runtime. The same four-question tool review was replayed through the local `/v1/systemone` endpoint four times consecutively per format; the median of the last three runs was taken. The four questions processed 2,020 input tokens in total and generated 0 tokens. Timing started when the local HTTP request was sent and ended when the decision result arrived.

| 4B format | GGUF download size | Median warm review latency |
| --- | ---: | ---: |
| Q4_K_M | 2.71 GB | 3.25 s |
| Q8_0 | 4.48 GB | 4.59 s |
| BF16 | 8.42 GB | 3.11 s |

BF16 took 0.14 seconds less than Q4_K_M for this request, with 5.72 GB larger weight files. After returning to the original Q4_K_M service, another measurement gave a warm median of 3.32 seconds.

Q4_K_M took 3.25 seconds with the default configuration. Explicitly enabling all-layer GPU offload and Flash Attention took 3.26 seconds; a standalone service with four slots under the same 8,192-token total context budget took 3,255 ms. All three configurations returned identical decisions and probabilities for this request. For consecutive tool calls, keep the model running and pass only the tool information needed for judgment, including risk signals and target parameters. Review retains the default 7-second wait budget.

**Control the wait for context compaction.** In QwenPaw's decision model compaction settings, adjust “Total timeout (seconds).” Local Q4_K_M measurements used a synthetic history containing an original order and old logs. Both inputs contained 10,432 tokens.

| Compaction total timeout | Time per compaction | Tokens after compaction |
| --- | ---: | ---: |
| 30 s | 24.02 s | 8,924 |
| 15 s | 12.02 s | 9,677 |

Both runs retained the original order, the last user request, and the six most recent messages. The shorter budget reduced the pause per round while leaving more original text for the next round. This setting affects compaction only; tool review has its own wait budget.

[Watch the QwenPaw tool review recording](https://decisionplayground.agentscope.io/piccolo.html#qwenpaw-showcase).

## Check the current selection

From the Piccolo repository, in a QwenPaw Python environment that supports this integration:

```bash
python scripts/check_qwenpaw_local.py
python -m pytest tests/test_qwenpaw_local.py
```

The check script sends only synthetic inputs. It does not execute example tools, download models, or modify configuration. Tests connect to a loopback protocol stub and do not replace actual model-quality or full-workflow evaluation.
