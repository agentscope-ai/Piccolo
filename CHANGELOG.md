# Changelog

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
- Marked ModelScope as an upcoming mirror; downloads currently use Hugging Face.

### Removed

- Obsolete Skill-based safety review, download helper, custom Guardian and their tests.

### Availability

- QwenPaw integration remains in Draft PR #8463 and requires its companion llama.cpp adaptation; it is not yet available in every released QwenPaw version.
- Training recipes and dataset publication remain coming soon. Hardware performance measurements remain follow-up work.
- Archived replay identities and existing commit author/committer metadata are preserved.
