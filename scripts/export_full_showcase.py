#!/usr/bin/env python3
"""Build complete read-only timelines from archived decisions and shared-engine receipts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'arena/web'
TARGET = WEB / 'showcase/full'
sys.path.insert(0, str(ROOT / 'arena'))
import blink_arena
from jev_engine_registry import get_engine
from jev_game_control import execute_push


def read(path):
    return json.loads(path.read_text())


def phase(name, before, after=None, frames=None, seconds=.5):
    result = {'name': name, 'before': before, 'after': after or before, 'seconds': seconds}
    if frames:
        # Consecutive deltas keep every physics tick without repeating the map.
        previous = {}
        deltas = []
        for frame in frames:
            deltas.append({k: v for k, v in frame.items() if k not in previous or previous[k] != v})
            previous = frame
        result['frames'] = deltas
    return result


def build(slug):
    completed = {'merge-2048': 'merge_2048', 'sokoban': 'sokoban_puzzle', 'tetris': 'tetris_placement'}
    if slug in completed:
        path = WEB / 'playground/data/home-decision.json'
        source = next(c for c in read(path)['clips'] if c['game'] == completed[slug])
        kind, title = source['game'], source['name_en']
        participants = [m['id'] for m in source['models']]
        initial, final, steps = source['initial_state'], source['final_state'], source['steps']
    else:
        path = WEB / f'showcase/traces/{slug}.json'
        source = read(path)
        kind = source['kind']
        title = {'mario': 'Mario', 'snake': 'Snake', 'jump-jump': 'Jump Jump', 'hex': 'Hex', 'dots-and-boxes': 'Dots & Boxes'}[slug]
        participants = source['participants']
        initial, final, steps = source['initial_state'], source['final_state'], source['steps']
    clip = {'id': slug, 'title': title, 'kind': kind, 'participants': participants,
            'source': str(path.relative_to(ROOT)), 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'initial_state': initial, 'final_state': final, 'result': source.get('result'), 'steps': []}
    snake_events = None
    if slug == 'snake':
        from export_snake_showcase import reconstruct_public, verify
        verify(source)
        snake_events = reconstruct_public(source) if source['replay'].get('state_projection') == 'public' else source['replay']['replay_events']
    mario = json.loads(subprocess.check_output(['node', str(ROOT / 'scripts/export_mario_frames.cjs'), str(path)])) if slug == 'mario' else None
    for i, saved in enumerate(steps):
        before = saved.get('before', saved.get('before_state', initial if i == 0 else clip['steps'][-1]['phases'][-1]['after']))
        after = saved.get('after', saved.get('state', saved.get('after_state')))
        candidates = saved.get('candidates')
        action = saved.get('action')
        applied = saved.get('action_applied', saved.get('execution', {}).get('action_applied', True))
        actor = saved.get('origin', 'model')
        phases = []
        if slug in ('mario', 'snake'):
            e = snake_events[i] if slug == 'snake' else source['replay']['replay_events'][i]
            before = e['before_state']
            candidates = list(e.get('record', {}).get('questions', {}).get('decision', {}).get('criteria', {}))
            actor = 'automatic' if e.get('no_request') else 'model'
        if candidates is None:
            candidates = list(get_engine(kind).observe(before)['questions']['decision']['criteria'])
        if action is not None and candidates:
            assert str(action) in candidates, (slug, i, action, candidates)
        if slug == 'mario':
            for name in ('pre', 'waiting', 'execution'):
                frames = mario[i][name]
                if len(frames) > 1 or name == 'execution':
                    phases.append(phase('choose' if name == 'waiting' else 'observe' if name == 'pre' else 'execute', frames[0], frames[-1], frames, max(.25, (frames[-1]['frame']-frames[0]['frame'])/60)))
        elif slug == 'snake':
            import jev_snake_realtime as snake
            # The trace contains every cell crossing; never discard intermediate moves.
            previous = snake.fresh(source['seed']) if i == 0 else snake_events[i-1]['after_state']
            for name, end in [('observe', e['before_state']), ('choose', e.get('arrival_state', e['before_state'])), ('execute', e['after_state'])]:
                frames = [snake.public(previous)]
                frames.extend({**snake.public(end), **f} for f in end['execution_trace']['frames'] if f['steps'] > previous['steps'])
                assert [f['steps'] for f in frames] == list(range(previous['steps'], end['steps']+1)), ('Missing Snake movement', i, name)
                frames.append(snake.public(end))
                phases.append(phase(name, frames[0], frames[-1], frames, max(.25, end['elapsed']-previous['elapsed'])))
                previous = end
        else:
            phases = [phase('observe', before, seconds=.3), phase('choose', before, seconds=.4)]
            frames = None
            seconds = .8
            if slug == 'sokoban':
                native = execute_push(before, action)
                assert native['player'] == after['player'] and sorted(native['boxes']) == sorted(after['boxes']) and native['steps'] == after['steps']
                frames = [{**before, **f} for f in native['execution_trace']['frames']]
                frames[-1] = after
                seconds = max(.8, (after['steps']-before['steps'])*.4)
            elif slug == 'tetris':
                state = before
                frames = [before]
                for delta in saved.get('execution_frames', []):
                    state = {**state, **delta}
                    frames.append(state)
                frames.append(after)
                seconds = max(.5, after['elapsed']-before['elapsed'])
            phases.append(phase('execute', before, after, frames, seconds))
        clip['steps'].append({'index': i, 'action': action, 'applied': applied, 'actor': actor,
                              'candidates': candidates, 'phases': phases})
    assert len(clip['steps']) == len(steps)
    clip['coverage'] = {'decisions': len(steps), 'indices': list(range(len(steps))),
                        'frame_receipts': sum(len(p.get('frames', [])) for s in clip['steps'] for p in s['phases'])}
    return clip


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', choices=['mario','snake','merge-2048','sokoban','tetris','jump-jump','hex','dots-and-boxes'])
    args = parser.parse_args()
    TARGET.mkdir(parents=True, exist_ok=True)
    slugs = ['mario','snake','merge-2048','sokoban','tetris','jump-jump','hex','dots-and-boxes']
    for slug in ([args.game] if args.game else slugs):
        clip = build(slug)
        (TARGET / f'{slug}.json').write_text(json.dumps(clip,ensure_ascii=False,separators=(',',':'))+'\n')
        print(json.dumps({'id':slug,**clip['coverage']}),flush=True)
    items = [{'id':s, 'trace':f'full/{s}.json'} for s in slugs]
    (WEB/'showcase/full-manifest.json').write_text(json.dumps({'items':items},indent=2)+'\n')
