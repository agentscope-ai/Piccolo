"""Regression checks for complete movement coverage and authentic Snake success."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from export_snake_showcase import verify
from export_showcase_probabilities import validate

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'arena/web/showcase'


def read(path):
    return json.loads(path.read_text())


def frames(phase):
    state = {}
    for delta in phase.get('frames', []):
        state = {**state, **delta}
        yield state


class FullShowcase(unittest.TestCase):
    def test_probabilities_cover_every_model_call_and_reject_wrong_receipts(self):
        count = 0
        for item in read(BASE/'full-manifest.json')['items']:
            clip = read(BASE/item['trace'])
            receipt = read(BASE/clip['probability_receipt'])
            count += validate(clip, receipt)
            for step, row in zip(clip['steps'], receipt['steps']):
                self.assertEqual(step['probabilities'], row['probabilities'])
            index = next(i for i, s in enumerate(clip['steps']) if s['actor'] == 'model')
            for mutation in ('action', 'candidate', 'sum', 'source'):
                bad = copy.deepcopy(receipt)
                if mutation == 'action': bad['steps'][index]['action'] = 'unrecorded-action'
                elif mutation == 'candidate': bad['steps'][index]['probabilities']['unrecorded-action'] = 0
                elif mutation == 'sum': bad['steps'][index]['probabilities'] = {k: 0 for k in bad['steps'][index]['probabilities']}
                else: bad['replay_source_sha256'] = 'wrong-source'
                with self.assertRaises(AssertionError): validate(clip, bad)
        self.assertEqual(count, 195)

    def test_success_is_our_verified_student(self):
        stream = read(BASE/'traces/snake.json')
        self.assertTrue(verify(stream)['verified'])
        self.assertEqual(stream['replay']['policy_origin'], 'student')
        self.assertTrue(stream['replay']['on_policy'])
        self.assertEqual(stream['replay']['rule_takeover_count'], 0)
        self.assertEqual(stream['final_state']['score'], 6)
        for mutate in ('loss', 'food', 'position'):
            bad = copy.deepcopy(stream)
            if mutate == 'loss': bad['result']['outcome'] = 'loss'
            elif mutate == 'food': bad['final_state']['score'] = 3
            else: bad['replay']['replay_events'][20]['after_state']['body'][0][0] += 1
            with self.assertRaises(AssertionError): verify(bad)

    def test_every_snake_cell_and_mario_tick(self):
        for slug, key, last in [('snake', 'steps', 49), ('mario', 'frame', 2083)]:
            clip = read(BASE/f'full/{slug}.json')
            seen = {frame[key] for s in clip['steps'] for p in s['phases'] for frame in frames(p)}
            self.assertEqual(seen, set(range(last+1)), slug)

    def test_sokoban_never_walks_through_a_wall(self):
        clip = read(BASE/'full/sokoban.json')
        moves = 0
        for s in clip['steps']:
            path = list(frames(s['phases'][-1]))
            for a, b in zip(path, path[1:]):
                self.assertEqual(sum(abs(x-y) for x,y in zip(a['player'],b['player'])), 1)
                self.assertNotIn(b['player'], b['walls'])
                self.assertNotIn(b['player'], b['boxes'])
                moves += 1
        self.assertEqual(moves, 14)

    def test_sources_and_all_steps_retained(self):
        total = 0
        for item in read(BASE/'full-manifest.json')['items']:
            clip = read(BASE/item['trace'])
            self.assertEqual(clip['source_sha256'], hashlib.sha256((ROOT/clip['source']).read_bytes()).hexdigest())
            self.assertEqual([s['index'] for s in clip['steps']], clip['coverage']['indices'])
            total += len(clip['steps'])
        self.assertEqual(total, 210)


if __name__ == '__main__':
    unittest.main()
