# Changelog

## 2026-11-02

- Added ModelScope download links for all 12 Piccolo releases.
- Updated the three-step QwenPaw guide and added a recorded local tool review.
- Linked the public DataJevBench repository from the Arena.

## v1.0.0 — 2026-10-30

First formal Piccolo source release.

### Added

- Apache-2.0 license for original project code, with third-party notices retained.
- Download links for Piccolo-4B, Piccolo-9B and Piccolo-27B: complete Safetensors plus BF16, Q8_0 and Q4_K_M GGUF variants on Hugging Face.
- Fixed model revisions and released-checkpoint benchmark summary.
- Full-checkpoint reference inference, a minimal decision request and native QwenPaw setup/checker.
- English and Chinese model-download, tool-review and compaction screenshots.
- Launch article covering data engineering, benchmarks and local agent use.

### Changed

- Aligned README files, model documentation and public entry points with the Piccolo release.
- Documented native candidate-token scoring, bidirectional prompt attention and the single managed local runtime.
- At launch, downloads were available on Hugging Face, with ModelScope planned.

### Removed

- Obsolete Skill-based safety review, download helper, custom Guardian and their tests.

### Availability

- At launch, QwenPaw integration was available in draft PR #8463 with a companion llama.cpp adaptation.
- Training recipes and dataset publication remain coming soon. Hardware performance measurements remain follow-up work.
- Archived replay identities and existing commit author/committer metadata are preserved.
