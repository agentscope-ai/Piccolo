# QwenPaw setup screenshots

The three setup screenshots show model download, decision-model approval and context compaction. The Chinese images are original 1290 × 747 browser captures from the local QwenPaw preview.

| Step | English screenshot | Chinese screenshot |
| --- | --- | --- |
| Download Piccolo | [Model download](en-model-download.jpg) | [Model download](zh-model-download.jpg) |
| Select decision-model approval | [Tool approval](en-automatic-review.jpg) | [Tool approval](zh-automatic-review.jpg) |
| Enable decision-model compaction | [Context compaction](en-context-compaction.jpg) | [Context compaction](zh-context-compaction.jpg) |

The English captures use the current QwenPaw settings interface at the same resolution. See the [English capture manifest](screenshots-20261103.json).

The [Chinese capture manifest](screenshots-20261029.json) records image dimensions, hashes and visible settings.

## Tool approval recording

The [15-second QwenPaw recording](https://decisionplayground.agentscope.io/piccolo.html#qwenpaw-showcase) shows two read-only Bash calls and a request to overwrite an existing report. Piccolo-4B-Q4_K_M approves the reads, then flags the overwrite as `destructive`. QwenPaw requests confirmation and the operator selects Deny. The original report remains unchanged.
