# Decision website source

The repository includes the bilingual homepage, leaderboards, release article, Method figures, recorded showcases and 12 interactive workflow examples.

## Run locally

The full combat video uses Git LFS. After cloning, run `git lfs install` and `git lfs pull`. CI source archives already include the complete video.

From the repository root, after installing the [Arena dependencies](../README.md):

```bash
python arena/scripts/preview_leaderboard.py --port 8080
```

Open `http://127.0.0.1:8080/` for the homepage, `/blog.html` for the article index, and `/piccolo.html` for the bilingual release article. This preview serves the recorded results and local media. Use the [Arena server](../README.md) to connect a model and play games.

## Edit and build

| Content | Source |
| --- | --- |
| Homepage and leaderboard | [`web/index.html`](../web/index.html), [`web/playground/`](../web/playground/) |
| English and Chinese article | [`web/blog/content.js`](../web/blog/content.js) |
| Method SVG figures | [`web/blog/architecture.js`](../web/blog/architecture.js), [`evolution.js`](../web/blog/evolution.js) |
| Original Method figures and video | [`web/blog/assets/`](../web/blog/assets/) |
| Six Harness and six Data cases | [`web/blog/workflow-cases.js`](../web/blog/workflow-cases.js) |
| Portable workflow examples | [`examples/workflows/`](../../examples/workflows/README.md) |
| Recorded game and QwenPaw gallery | [`web/blog/gallery.js`](../web/blog/gallery.js) |
| Media hashes and public URLs | [`website-assets.json`](website-assets.json) |

Node.js 22 is sufficient for article generation; KaTeX and fonts are bundled.

```bash
node arena/scripts/render_blog.mjs
node arena/scripts/render_blog.mjs --check
node arena/scripts/build_blog_profiles.mjs --check
node arena/scripts/export_workflow_cases.mjs --check
node --test arena/tests/blog_evidence.test.cjs arena/tests/workflow_demos.test.cjs
```

`render_blog.mjs` updates the English HTML, generated SVGs and versioned browser imports. The language switch loads Chinese text from the same content module. The figure-profile script reads the existing Arena leaderboard JSON files.

## Media and attribution

All article media are included locally, including full game GIFs, the QwenPaw recordings, Method figures and the complete combat video. Keep the source notices in [`demo-data-cases/`](demo-data-cases/), [`workflow-data-license.txt`](../web/blog/workflow-data-license.txt), the bundled KaTeX license, and [third-party notices](THIRD_PARTY.md).
