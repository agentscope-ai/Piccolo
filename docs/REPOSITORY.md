# Piccolo Repository Scope

## Current source release

This official source release includes public download links for three model sizes, pinned weight revisions, reference inference, published results, native QwenPaw integration documentation, the interactive Arena, and archived replays. Entry points are [Decision](https://decisionplayground.agentscope.io/), [GitHub](https://github.com/agentscope-ai/Piccolo), and the [model download catalog](MODELS.md).

- The [README](../README_zh.md) is the starting point; the [release blog](piccolo-blog.md) is the master draft for WeChat Official Accounts and Xiaohongshu.
- The [website source](../arena/docs/WEBSITE.md) includes the bilingual article, Method figures, complete replays, and [12 workflow examples](../examples/workflows/README.md).
- [models/](../models/README.md) pins weight revisions for 12 model repositories. Complete Safetensors, BF16, Q8_0, and Q4_K_M releases are available.
- [inference/](../inference/README.md) and [examples/](../examples/README.md) provide reference inference for candidate probabilities and minimal requests.
- [evaluation/](../evaluation/README.md) provides benchmark results and one-command reproduction scripts. Selected historical replays retain their own checkpoint identities.

Native downloading, decision model selection, approval, and ReMe compaction are integrated into [QwenPaw main](https://github.com/agentscope-ai/QwenPaw/blob/main/docs/local-piccolo.md), using bidirectional prompt attention and candidate-token scoring. See the [QwenPaw guide](QWENPAW.md) for source installation and compatible runtime setup.

Our own code uses [Apache-2.0](../LICENSE). Third-party licenses and attribution are listed in [NOTICE](../NOTICE) and [component sources](../arena/docs/THIRD_PARTY.md). Historical protocols, the `blink_arena` Python package, trajectory identities, and commit author metadata are preserved; history has not been rewritten for this release.

## Migration and verification

Arena originated from JevArena and retains the shared engines, HTTP interfaces, public leaderboards, and real replays. The source release and website deployment are separate artifacts and should be checked separately. See the [CHANGELOG](../CHANGELOG.md) for this release's changes and the [Arena release checks](../arena/docs/RELEASE_CHECK.md) for verification commands.

## Continuous integration

[GitHub Actions](../.github/workflows/ci.yml) automatically runs Python, frontend, and browser tests on main-branch updates and PRs, checks local links and generated files, and packages the complete source. Build artifacts are stored in Actions; no GitHub Release is created.
