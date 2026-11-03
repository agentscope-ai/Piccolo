# Changelog

## 2026-11-03 — Website source and reproducible tooling

- Sync Arena with the latest website source and its 17-game playground.
- Include the bilingual article, Method figures, recorded media and 12 workflow examples.
- Add one-command evaluation using the official benchmark runners and scorers.
- Add CI for tests, links, generated assets, browser checks and source packaging.
- Publish English QwenPaw setup screenshots and English subdirectory READMEs.
- Remove the old GitHub Release; source packages are available from Actions.

## 2026-11-03

- Synchronized all four benchmark snapshots, release results and bilingual score tables with the Decision website.
- Documented the SGLang service entry point and bundled its FlexDM and Decision Index notices.

- Removed empty training and dataset placeholders and their publication promises.
- Removed obsolete unreleased-benchmark UI branches and updated stale release wording.
- Linked published benchmark reproduction guides and the existing local latency measurements.

## 2026-11-02

- Added ModelScope download links for all 12 Piccolo releases.
- Updated the three-step QwenPaw guide and linked the English QwenPaw screen recording in the Piccolo blog.
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
- Training recipes and datasets were outside the source release. Hardware measurements were limited to the recorded validation runs.
- Archived replay identities and existing commit author/committer metadata are preserved.
