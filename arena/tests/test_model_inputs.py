"""Regression checks for public prediction facts, candidate identity and UI wire inputs."""
import copy
import json
import os
from pathlib import Path
import unittest

import blink_arena
from blink_arena.model_inputs import lossless_record as compact_record, LOSSLESS_REVISION as REVISION, _pack, _table
from blink_arena.engine import get_engine


def unpack(value):
    """Independent decoder used to compare every structured prediction field."""
    if isinstance(value, list):
        return [unpack(item) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {'groups'}:
        result = {}
        for group in value['groups']:
            result.update(unpack(group))
        return result
    if {'columns', 'rows'} <= set(value) <= {'columns', 'rows', 'defaults', 'key'}:
        result = []
        for row in value['rows']:
            flat = {**value.get('defaults', {}), **dict(zip(value['columns'], row, strict=True))}
            item = {}
            for path, cell in flat.items():
                obj = item
                parts = path.split('.')
                for part in parts[:-1]:
                    obj = obj.setdefault(part, {})
                obj[parts[-1]] = unpack(cell)
            result.append(item)
        if 'key' in value:
            return {row.pop(value['key']): row for row in result}
        return result
    return {key: unpack(item) for key, item in value.items()}


class ModelInputTests(unittest.TestCase):
    def test_tables_preserve_false_null_empty_and_heterogeneous_predictions(self):
        facts = {
            'a': {'x': 1, 'risk': False, 'nested': {'value': None}, 'source': 'visible' * 50},
            'b': {'x': 2, 'risk': True, 'nested': {'value': None}, 'source': 'visible' * 50},
            'c': {'x': 3, 'risk': False, 'extra': {}, 'source': 'visible' * 50},
        }
        self.assertEqual(unpack(_table(facts, keyed=True)), facts)
        rows = [{'action': 'a', 'result': False}, {'action': 'b', 'result': None}]
        self.assertEqual(unpack(_pack(rows)), rows)

    def test_gomoku_keeps_all_threats_candidates_and_coordinate_facts(self):
        engine = __import__('jev_engine_registry').get_archived_engine('gomoku_19x19')
        state = engine.reset(2026102116)
        old = engine.observe(state)
        saved = copy.deepcopy(old)
        new = compact_record(old)
        self.assertEqual(old, saved)
        self.assertEqual(unpack(new['state']['candidate_consequences']), old['state']['candidate_consequences'])
        self.assertEqual(new['state']['opponent_immediate_winning_moves'], old['state']['opponent_immediate_winning_moves'])
        self.assertEqual(new['state']['rules'], old['state']['rules'])
        self.assertEqual(list(new['questions']['decision']['criteria']), list(old['questions']['decision']['criteria']))
        self.assertEqual(new['questions']['decision']['option_order'], old['questions']['decision']['option_order'])
        self.assertIs(compact_record(new), new)

    def test_real_large_mario_preserves_every_prediction_and_control_value(self):
        observation = json.loads((Path(__file__).parent / 'fixtures/mario_large_observation.json').read_text())
        old = get_engine('mario_platformer').observe(observation)
        new = compact_record(old)
        actual = unpack(new['state'])
        expected = copy.deepcopy(old['state'])
        if 'recent_effects' not in actual['control']:
            actual['control']['recent_effects'] = actual['observation']['action_execution']['recent_effects']
        actual.pop('encoding'); actual.pop('model_input_revision')
        actual.pop('field_aliases', None)
        self.assertEqual(actual, expected)
        self.assertEqual(new['questions']['decision']['instructions'], old['questions']['decision']['instructions'])
        self.assertEqual(new['questions']['decision']['option_order'], old['questions']['decision']['option_order'])
        self.assertLess(max(map(len, new['questions']['decision']['criteria'].values())), 150)

    def test_real_terra_preserves_geometry_upgrades_failed_targets_and_forecasts(self):
        from jev_terraria_contract import expand_record
        cases = json.loads((Path(__file__).parent / 'fixtures/terra_compact_public_states.json').read_text())['cases']
        for case in cases:
            old = get_engine('terraria_survival').observe(case['observation'])
            expected = expand_record(old)['state']
            new = compact_record(old)
            actual = unpack(new['state'])
            for src, dst in (
                (('control', 'recent_effects'), ('observation', 'control', 'recent_effects')),
                (('navigation', 'recent_actual_effects'), ('observation', 'last_effects')),
                (('navigation', 'progression'), ('observation', 'progression')),
                (('navigation', 'tool_targets'), ('observation', 'tool_targets')),
                (('navigation', 'objective'), ('observation', 'objective')),
            ):
                if src[-1] not in actual[src[0]]:
                    item = actual
                    for part in dst:
                        item = item[part]
                    actual[src[0]][src[-1]] = copy.deepcopy(item)
            actual.pop('encoding'); actual.pop('model_input_revision')
            actual.pop('field_aliases', None)
            self.assertEqual(actual, expected)
            self.assertEqual(new['questions']['decision']['instructions'], expand_record(old)['questions']['decision']['instructions'])
            self.assertEqual(new['questions']['decision']['option_order'], old['questions']['decision']['option_order'])

    def test_small_unrelated_game_is_unchanged(self):
        engine = get_engine('checkers')
        old = engine.observe(engine.reset(42))
        self.assertEqual(compact_record(old), old)

    def test_non_game_questions_pass_through(self):
        from blink_arena.model_inputs import project_record
        record = {'state': {'text': 'sample'}, 'questions': {'rating': {'type': 'score'}}}
        self.assertIs(project_record(record), record)
        record['metadata'] = {'sub_domain': 'gomoku_19x19'}
        self.assertIs(project_record(record), record)

    def test_original_evaluator_record_is_not_changed_by_frontend_projection(self):
        from jev_demo_showcases import as_record
        from blink_arena.model_inputs import project_record
        engine = get_engine('sokoban_puzzle'); state = engine.reset(42)
        native = as_record(state)
        self.assertEqual(native, engine.observe(state))
        self.assertIs(project_record(native, 'original'), native)
        self.assertNotEqual(project_record(native), native)

    def test_board_frontend_receipt_is_the_actual_request_before_the_move(self):
        from blink_arena.model_inputs import REVISION
        from fastapi.testclient import TestClient
        from blink_arena.app import create_app
        from blink_arena.schemas import AppConfig
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(data=Path(directory), config=AppConfig())
            sent = []
            async def predict(record, qid, model=None):
                sent.append(copy.deepcopy(record))
                return {'value': next(iter(record['questions'][qid]['criteria'])), 'model': model, 'served_model': model}
            app.state.providers.predict = predict
            with TestClient(app) as client:
                response = client.post('/api/v1/connections', json={'model_id': 'fixture', 'name': 'Fixture',
                    'served_model': 'fixture', 'adapter': 'decision'})
                self.assertEqual(response.status_code, 201)
                initial = client.post('/api/game/new', json={'kind': 'othello_6x6', 'seed': 2026102116}).json()
                response = client.post('/api/game/move', headers={'X-Demo-Model': 'fixture'}, json={
                    'session_id': initial['session_id'], 'revision': initial['revision'], 'model': True})
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                self.assertNotIn('model_input_revision', sent[0]['state'])
                self.assertEqual(result['previous_input']['state'], sent[0]['state'])
                self.assertEqual(result['previous_input']['option'], sent[0]['questions']['decision']['criteria'])
                self.assertNotEqual(result['previous_input']['state']['board'], result['input']['state']['board'])


class IntentDecisionTests(unittest.TestCase):
    def test_selected_profile_keeps_regressed_games_original(self):
        for game in ('othello_6x6', 'hex_7x7'):
            engine = get_engine(game); state = engine.reset(42)
            self.assertEqual(engine.model_input(state), engine.observe(state))
            self.assertNotEqual(engine.model_input(state, input_format='intent-v2'), engine.observe(state))

    def test_selected_mario_keeps_original_guidance_and_all_predictions(self):
        observation = json.loads((Path(__file__).parent / 'fixtures/mario_large_observation.json').read_text())
        engine = get_engine('mario_platformer'); old = engine.observe(observation)
        chosen = engine.model_input(observation)
        self.assertEqual(chosen, compact_record(old))
        self.assertEqual(chosen['questions']['decision']['instructions'], old['questions']['decision']['instructions'])
        self.assertEqual(unpack(chosen['state']['observation']['candidate_effects']), old['state']['observation']['candidate_effects'])

    def test_mario_keeps_risks_delay_and_landing_choices_without_executor_internals(self):
        from blink_arena.model_inputs import compact_record as project
        observation = json.loads((Path(__file__).parent / 'fixtures/mario_large_observation.json').read_text())
        engine = get_engine('mario_platformer')
        old = engine.observe(observation); saved = copy.deepcopy(old)
        new = project(old)
        self.assertEqual(engine.model_input(observation, input_format='intent-v2'), new)
        for action, facts in old['state']['observation']['candidate_effects'].items():
            prediction = new['state']['predictions'][action]
            self.assertEqual(prediction['landing'], facts['predicted_player'])
            for source, target in (('plant_or_enemy_risk', 'collision'), ('visible_pit_fall', 'pit'),
                ('head_collision', 'head'), ('unknown_terrain', 'unknown'), ('landing_plant_exposure', 'flower_at_landing')):
                if source in facts:
                    self.assertEqual(prediction['risk'][target], facts[source])
            for actual, expected in zip(prediction.get('delay_scenarios', []), facts.get('latency_scenarios', []), strict=True):
                for source, target in (('assumed_wait_seconds', 'wait_s'), ('arrival_dynamic_risk_estimate', 'arrival_risk'),
                    ('post_landing_idle_risk_estimate', 'idle_risk'), ('post_landing_pit', 'pit')):
                    if source in expected:
                        self.assertEqual(actual[target], expected[source])
            for source, target in (('visible_forward_landing_regions', 'forward'), ('visible_retreat_landing_regions', 'retreat')):
                if source in facts.get('continuation', {}):
                    self.assertEqual(prediction['next_jump'][target],
                        [{k: row[k] for k in ('left','right','top')} for row in facts['continuation'][source]])
        self.assertEqual(old, saved)
        self.assertEqual(list(new['questions']['decision']['criteria']), list(old['questions']['decision']['criteria']))
        self.assertEqual(new['questions']['decision']['option_order'], old['questions']['decision']['option_order'])

    def test_terra_preserves_combat_resource_forecasts_and_gate_requirements(self):
        from blink_arena.model_inputs import compact_record as project
        from jev_terraria_contract import expand_record
        cases = json.loads((Path(__file__).parent / 'fixtures/terra_compact_public_states.json').read_text())['cases']
        for case in cases:
            old = get_engine('terraria_survival').observe(case['observation'])
            original = expand_record(old)['state']; new = project(old)['state']
            self.assertEqual(new['world']['objective'], original['observation']['objective'])
            self.assertEqual(new['upgrades'], original['navigation']['upgrade_rules'])
            for action, facts in original['navigation']['collection'].items():
                self.assertEqual(new['collection'][action]['successful_collection_effect'], facts['successful_collection_effect'])
                self.assertEqual(new['collection'][action]['previous_failed_attempts'], facts['previous_failed_attempts'])
            for actual, expected in zip(new['combat'], original['navigation']['combat'], strict=True):
                for field in ('enemy', 'contact_damage_under_current_buffs', 'minimum_attacks_to_defeat_if_all_hit',
                              'hits_to_player_death_without_healing'):
                    self.assertEqual(actual[field], expected[field])
                self.assertEqual(actual['attack']['hitting_directions'], expected['native_attack']['hitting_directions'])
                self.assertEqual(actual['attack']['geometrically_in_range'], expected['native_attack']['geometrically_in_range'])
                self.assertNotIn('rectangles_tiles', actual['attack'])

    def test_gomoku_preserves_wins_replies_lines_and_all_candidate_ids(self):
        from blink_arena.model_inputs import compact_record as project
        engine = __import__('jev_engine_registry').get_archived_engine('gomoku_19x19'); old = engine.observe(engine.reset(2026102116)); new = project(old)
        for action, facts in old['state']['candidate_consequences'].items():
            projected = new['state']['candidate_consequences'][action]
            self.assertEqual(projected, {'win': facts['wins_now'], 'opponent_wins': facts['opponent_immediate_winning_replies'],
                                         'line': facts['max_own_contiguous_line_after']})
            x,y=map(int,action.split(','));self.assertEqual((19-y,x-1),(facts['landing_row'],facts['landing_col']))
        self.assertEqual(new['questions']['decision']['option_order'], old['questions']['decision']['option_order'])


if __name__ == '__main__':
    unittest.main()
