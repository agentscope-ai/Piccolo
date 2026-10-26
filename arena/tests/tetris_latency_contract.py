"""CPU regression for visible delayed outcomes, stale intent safety and credit audit."""
import copy
import json
from pathlib import Path
import unittest

import blink_arena
import jev_tetris_realtime as game
from jev_tetris_projection import candidate_predictions, control_window, project_candidate
from jev_tetris_rl import rebuild_credit
from jev_tetris_runtime import discard_reason


class LatencyContractTests(unittest.TestCase):
    def test_calibrated_scenarios_are_visible_and_window_is_current_piece_only(self):
        initial=game.fresh(41)
        self.assertIsNone(control_window(game.public(initial))['seconds_to_lock_without_new_input'])
        state=game.step(initial,'0:0')
        visible=game.public(state)
        original=copy.deepcopy(visible)
        scenarios=candidate_predictions(visible)
        self.assertEqual([v['response_delay_seconds'] for v in scenarios['0:0']['latency_scenarios']],[3.2,7.])
        self.assertEqual(visible,original)
        window=control_window(visible)
        self.assertGreater(window['seconds_to_lock_without_new_input'],0)
        self.assertFalse(window['new_piece_control_authorized'])
        self.assertEqual(window['piece_id'],visible['active']['piece_id'])
        record=game.as_record(state)
        self.assertEqual(record['state']['timing']['control_window'],window)
        self.assertIn('延迟7秒',record['questions']['decision']['criteria']['0:0'])

    def test_late_response_never_controls_future_piece(self):
        state=game.step(game.fresh(41),'0:0')
        waiting=game.advance_idle(state,8.)
        visible=game.public(waiting)
        self.assertEqual(waiting['active']['piece_id'],1)
        window=control_window(visible)
        self.assertLess(window['seconds_to_lock_without_new_input'],1)
        action=list(game.placement_choices(visible))[-1]
        facts=project_candidate(visible,action,response_delay=7.)
        self.assertFalse(facts['action_applied'])
        self.assertEqual(facts['scope'],'current_piece_only_no_future_spawn_no_probability')
        self.assertIsNone(facts['landing'].get('future_piece'))
        arrived=game.advance_idle(waiting,7.)
        self.assertEqual(discard_reason(waiting,arrived,action),'piece_changed_while_waiting')
        self.assertGreater(arrived['active']['piece_id'],1)

    def test_projection_rejects_private_fields_and_never_queries_future_bag(self):
        from unittest.mock import patch
        state=game.step(game.fresh(18),'0:0')
        with self.assertRaises(ValueError):candidate_predictions(state)
        visible=game.public(state)
        visible.pop('next_piece',None)
        with patch.object(game,'_piece',side_effect=AssertionError('future random sequence forbidden')):
            facts=project_candidate(visible,'0:1',response_delay=7.)
            self.assertIsNone(facts['visible_next_piece_spawn_clear'])
            control_window(visible)

    def test_multilock_credit_marks_uncontrolled_wait_without_removing_terminal_cost(self):
        initial=game.fresh(18);arrival=copy.deepcopy(initial)
        after=copy.deepcopy(initial);after.update(steps=3,elapsed=29.,outcome='loss')
        event={'ordinal':5,'action_applied':True,'arrival_state':arrival}
        trace,extra=rebuild_credit(initial,[{'ordinal':5,'action':'0:0'}],after,{'replay_events':[event]})
        self.assertEqual(trace[0]['credit_before_state'],arrival)
        self.assertEqual(trace[0]['credit_after_state'],after)
        audit=trace[0]['control_ownership']
        self.assertEqual(audit['credit_locked_piece_ids'],[1,2,3])
        self.assertEqual(audit['controlled_piece_locks'],1)
        self.assertEqual(audit['uncontrolled_piece_ids'],[2,3])
        self.assertTrue(audit['terminal_cost_preserved'])
        self.assertEqual(json.loads(json.dumps(trace))[0]['control_ownership'],audit)

    def test_new_revision_preserves_v3_physics_exactly(self):
        a=game.fresh(18);b=game.fresh(18,revision=game.LEGACY_PERSISTENT_REVISION)
        for action in ['0:0','0:1','0:2','0:3']:
            if a['outcome']:break
            a=game.step(a,action);b=game.step(b,action)
            for wait in [1.,3.2,7.]:
                a=game.advance_idle(a,wait);b=game.advance_idle(b,wait)
                expected=copy.deepcopy(a);expected['engine_revision']=game.LEGACY_PERSISTENT_REVISION
                self.assertEqual(expected,b)

    def test_legacy_record_has_original_revision_without_new_scenarios(self):
        state=game.fresh(18,revision=game.LEGACY_PERSISTENT_REVISION)
        record=game.as_record(state)
        self.assertEqual(record['provenance']['candidate_revision'],'tetris-visible-intent-consequences-v1')
        self.assertNotIn('control_window',record['state']['timing'])
        self.assertTrue(all('延迟7秒' not in value for value in record['questions']['decision']['criteria'].values()))

    def test_browser_recognizes_v4_realtime_state(self):
        source=(Path(__file__).resolve().parents[1]/'web/playground/tetris-live.js').read_text()
        self.assertIn(game.REVISION,source)

if __name__=='__main__':unittest.main()
