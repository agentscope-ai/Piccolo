#!/usr/bin/env node
import {readFile, writeFile} from 'node:fs/promises';
import {workflowCases} from '../web/blog/workflow-cases.js';
const target = new URL('../../examples/workflows/cases.json', import.meta.url);
const output = JSON.stringify({schema_version: 'piccolo.workflow-examples.v1', languages: ['en', 'zh'], cases: workflowCases}, null, 2) + '\n';
if (process.argv.includes('--check')) {
  if (await readFile(target, 'utf8') !== output) throw Error('Workflow examples differ from the website; run node arena/scripts/export_workflow_cases.mjs.');
  console.log('All 12 bilingual workflow cases match the website.');
} else {
  await writeFile(target, output);
  console.log('Exported 6 Harness and 6 Data workflow cases.');
}
