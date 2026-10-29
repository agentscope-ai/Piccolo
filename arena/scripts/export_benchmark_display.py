#!/usr/bin/env python3
"""Apply the website presentation policy without changing evaluation evidence."""
import argparse
import json
from pathlib import Path

BENCHMARKS = ('harnessjevbench', 'datajevbench', 'jevbench', 'decisionindex')
EXCLUDED = {
    'access-StartLux-Decision-v1.1-27B-AutoThink',
    'access-qwen38-27b',
    'access-qwen3.8-27b-chat-Direct-v1',
    'access-qwen3.8-27b-chat-Thinking-v1',
    'access-qwen3.8-27b-historical-chat-API',
}
DATA_LABELS = [
    ('Data Filtering', '数据准入与过滤'),
    ('Operator Selection', '算子与处理方案选择'),
    ('Quality Assessment', '数据产物质量评估'),
    ('Information Sufficiency', '所需信息充分性'),
    ('Evidence & Privacy', '结论核验与隐私审查'),
    ('Data-workflow Control', '数据任务决策'),
]


def present(document):
    document = json.loads(json.dumps(document))
    ident = document['benchmark_id']
    document['rows'] = [row for row in document['rows'] if row['model_id'] not in EXCLUDED]
    if ident == 'jevbench':
        document['title'] = 'JevBench Public'
    elif ident == 'decisionindex':
        document['title'] = 'Decision Index Public'
    for row in document['rows']:
        if row['model_id'] in {'ours-w22m05r02-v5best-avg50', 'oneshot-w22m05r02-v5best-avg50'} or row['model_name'] == 'Ours':
            row['model_name'] = 'Blink (27B)'
            row['notes'] = [note.replace('Ours', 'Blink (27B)') for note in row.get('notes', [])]
        for axis in row.get('axes', []):
            if ident == 'harnessjevbench':
                axis['label_en'] = axis['id'].replace('_', ' ').title()
            elif ident == 'datajevbench':
                axis['label_en'], axis['label_zh'] = DATA_LABELS[int(axis['id'][1:]) - 1]
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True, help='Frozen website-format export; never raw experiment files')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.source_dir.resolve() == args.output_dir.resolve():
        parser.error('Use separate input and output directories to preserve the source export')
    documents = {name: present(json.loads((args.source_dir / f'{name}.json').read_text())) for name in BENCHMARKS}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, document in documents.items():
        path = args.output_dir / f'{name}.json'
        temporary = path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n')
        temporary.replace(path)
        print(f'{name}: {len(document["rows"])} models -> {path}')


if __name__ == '__main__':
    main()
