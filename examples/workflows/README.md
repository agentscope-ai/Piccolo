# Workflow examples

[Download the 12 bilingual cases](cases.json) used by the [Piccolo website](https://decisionplayground.agentscope.io/piccolo.html): six agent-harness decisions and six data-workflow decisions.

| Agent harness | Data workflow |
| --- | --- |
| Tool selection | Data filtering |
| Model routing | Operator selection |
| Context retention | Artifact quality |
| Permission review | Information sufficiency |
| Completion verification | Evidence and privacy |
| Failure recovery | Next workflow action |

Each case contains a state, question, candidates, reference choice and explanation. Bilingual presentation fields use `[English, Chinese]`; `answer` is the zero-based reference option index. `source_id` and `source_url` identify the source. The model-routing case uses illustrative model configurations.

- [Website case source](../../arena/web/blog/workflow-cases.js)
- [Interactive renderer](../../arena/web/blog/workflow-demos.js)
- [Six DataJevBench source records](../../arena/docs/demo-data-cases/selected-records.json)
- [Data source license and attribution](../../arena/docs/demo-data-cases/LICENSE.txt)

Regenerate the JSON after editing the website examples:

```bash
node arena/scripts/export_workflow_cases.mjs
node arena/scripts/export_workflow_cases.mjs --check
```
