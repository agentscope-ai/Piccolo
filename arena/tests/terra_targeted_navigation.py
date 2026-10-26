"""Real-physics navigation/target tests; fixtures are never training victories."""
from __future__ import annotations

import argparse
import asyncio
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

from playwright.async_api import async_playwright
from terra_core_test_support import engine_source, test_source, install_fixture

PACKAGE = Path(__file__).resolve().parents[1]


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


async def main(args):
    package = args.package.resolve()
    sys.path.insert(0, str(package))
    import blink_arena  # noqa: F401: registers this repository's engine imports.
    import jev_terraria_contract as contract
    import jev_world_realtime_rl as world

    assert Path(contract.__file__).resolve().is_relative_to(package)
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
        Quiet, directory=str(package / 'web')))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    checks, rows = {}, {}
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await install_fixture(page, package);await page.add_init_script('window.__JEV_TEST_MODE__=true;')
                await page.goto(base + '/playground/terraria.html')
                scenarios = [
                    {'name': 'left_without_enemy', 'action': 'explore_left',
                     'fixture': {'x': 20, 'y': 13.75}},
                    {'name': 'left_mines_visible_wall', 'action': 'explore_left',
                     'fixture': {'x': 20, 'y': 13.75, 'pick': 8,
                                 'tiles': [[18, 13, 1], [18, 14, 1]]}},
                    {'name': 'descend_to_guardian', 'action': 'approach_guardian',
                     'fixture': {'x': 10, 'y': 13.75, 'pick': 8,
                                 'tiles': [[x, 21, 11] for x in range(5, 18)],
                                 'enemies': [{'x': 10.5*16, 'y': 19.75*16}]}},
                    {'name': 'ascend_to_guardian', 'action': 'approach_guardian',
                     'fixture': {'x': 10, 'y': 13.75, 'dirt': 15, 'pick': 8,
                                 'tiles': [[x, 7, 1] for x in range(6, 17)],
                                 'enemies': [{'x': 10.5*16, 'y': 5.75*16}]}},
                    {'name': 'guard_not_nearest', 'action': 'fight_guardian',
                     'fixture': {'x': 10, 'y': 13.75,
                                 'enemies': [{'x': 12*16, 'y': 13.75*16, 'hp': 9},
                                             {'x': 9.8*16, 'y': 13.75*16,
                                              'gateGuardian': False, 'hp': 1000}]}},
                    {'name': 'guard_lost_before_execution', 'action': 'fight_guardian',
                     'fixture': {'x': 10, 'y': 13.75,
                                 'enemies': [{'x': 100*16, 'y': 13.75*16}]}},
                ]
                for scenario in scenarios:
                    row = await page.evaluate('''async s=>{
                      const api=JevTerramai,extra=s.fixture,tiles=extra.tiles||[];
                      const enemies=(extra.enemies||[]).map(e=>Object.assign({kind:'zombie',
                        gateGuardian:true,boss:false,x:0,y:0,w:14,h:20,hp:1000,maxhp:1000,
                        lv:1,vx:0,vy:0,t:0,hop:999,face:1,ground:true},e));
                      api.fixture(Object.assign({dirt:10},extra,{
                        tiles:Array.from({length:70},(_,x)=>[x,15,1]).concat(tiles),enemies}));
                      api.activate(true);const before=structuredClone(api.prepare({clock:'step'}));
                      const after=structuredClone(await api.act(s.action));api.activate(false);
                      return {before,after,render_error:window.jevRenderError||null};
                    }''', scenario)
                    row['record'] = contract.as_record(row['before'])
                    name = scenario['name']; rows[name] = row
                    checks[name + ':no_takeover'] = row['after']['execution_audit']['rule_takeover_count'] == 0
                    checks[name + ':one_choice'] = row['after']['decisions'] == 1
                    checks[name + ':no_render_error'] = not row['render_error']
                left = rows['left_without_enemy']
                checks['left_without_enemy:available'] = 'explore_left' in left['record']['questions']['decision']['criteria']
                checks['left_without_enemy:real_displacement'] = left['after']['player']['x'] < left['before']['player']['x']-2
                wall = rows['left_mines_visible_wall']
                checks['left_wall:real_displacement'] = wall['after']['player']['x'] < 18
                checks['left_wall:terrain_changed'] = wall['after']['control']['recent_effects'][-1]['net_terrain_changes'] > 0
                down = rows['descend_to_guardian']
                checks['descent:real_height_change'] = down['after']['player']['y'] > down['before']['player']['y']+2
                checks['descent:real_mining'] = down['after']['control']['recent_effects'][-1]['net_terrain_changes'] > 0
                checks['descent:no_automatic_attack'] = down['after']['progression']['player_attack_hits'] == 0
                up = rows['ascend_to_guardian']
                checks['ascent:real_height_change'] = up['after']['player']['y'] < up['before']['player']['y']-2
                checks['ascent:charged_supports'] = up['after']['control']['execution_counts']['placed'] > 0
                checks['ascent:no_automatic_attack'] = up['after']['progression']['player_attack_hits'] == 0
                bound = rows['guard_not_nearest']; facts = bound['record']['state']['navigation']['guardian_target']
                checks['guardian:target_matches_public_contract'] = bound['after']['control']['target']['id'] == facts['target']['id']
                checks['guardian:nearest_ordinary_not_substituted'] = facts['target']['id'] != contract.nearest_visible_enemy(bound['before'])['id']
                checks['guardian:actual_native_damage'] = bound['after']['progression']['guardian_player_kills'] == 1
                missing = rows['guard_lost_before_execution']
                checks['missing:no_hidden_candidate'] = 'fight_guardian' not in missing['record']['questions']['decision']['criteria']
                checks['missing:honest_feedback'] = missing['after']['control']['events'] == ['target_missing']
                checks['missing:no_hidden_memory'] = not missing['before']['known_guardians']
                memory = await page.evaluate('''async()=>{
                  const api=JevTerramai;
                  api.fixture({x:20,y:13.75,dirt:5,tiles:Array.from({length:80},(_,x)=>[x,15,11]),
                    enemies:[{kind:'zombie',gateGuardian:true,boss:false,x:22*16,y:13.75*16,w:14,h:20,
                      lv:1,vx:0,vy:0,hp:1000,maxhp:1000,t:0,hop:999,face:1,ground:true}]});
                  const unobserved=structuredClone(api.snapshot());api.activate(true);
                  const observed=structuredClone(api.prepare({clock:'step'}));api.probe('move_left',180);
                  const outOfView=structuredClone(api.prepare({clock:'step'}));api.activate(false);
                  const reset=api.reset(2026101718);return {unobserved,observed,outOfView,reset};
                }''')
                rows['memory'] = memory
                checks['memory:only_observation_creates_history'] = not memory['unobserved']['known_guardians'] and bool(memory['observed']['known_guardians'])
                checks['memory:not_updated_out_of_view'] = not memory['outOfView']['enemies'] and memory['outOfView']['known_guardians'] == memory['observed']['known_guardians']
                checks['memory:reset_clears_sightings'] = not memory['reset']['known_guardians']
                checks['memory:python_exposes_stale_target'] = contract.guardian_target_facts(memory['outOfView'])['target']['visible'] is False
                await page.close()

                class Sampler:
                    args = SimpleNamespace(frontend=base)
                    async def policy_action(self, record, episode_id, ordinal):
                        await asyncio.sleep(.05)
                        return ('explore_left' if ordinal % 2 == 0 else 'explore_right'), {'forced': False, 'origin': 'test_only'}
                sampler = Sampler(); sampler.browser = browser
                previous_limit = world.LIMITS.get('terraria_survival')
                world.LIMITS['terraria_survival'] = 3
                try:
                    job = {'kind': 'terraria_survival', 'seed': 2022140200, 'episode_id': 'navigation-test-only'}
                    initial, final, trace, outcome, extra = await world.play(sampler, job)
                    await world.verify(sampler, job, initial, final, extra, trace)
                    checks['replay:exact_native_frame_replay'] = extra.get('status', 'complete') == 'complete' and outcome == 'budget_exhausted'
                    checks['replay:real_time_continues'] = any(e['arrival_state']['frame'] > e['before_state']['frame'] for e in extra['replay_events'])
                    rows['replay'] = {'initial': initial, 'final': final, 'outcome': outcome, 'events': len(extra['replay_events'])}
                finally:
                    if previous_limit is None:world.LIMITS.pop('terraria_survival', None)
                    else:world.LIMITS['terraria_survival'] = previous_limit
            finally:
                await browser.close()
    finally:
        await asyncio.to_thread(server.shutdown); server.server_close(); thread.join(timeout=2)
    result = {'passed': all(checks.values()), 'checks': checks, 'rows': rows,
              'real_chromium': True, 'model_calls': 0, 'test_fixtures_are_not_training_successes': True}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'passed': result['passed'], 'checks': len(checks), 'failed': [k for k,v in checks.items() if not v]}), flush=True)
    return int(not result['passed'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, default=PACKAGE)
    parser.add_argument('--out', type=Path, required=True)
    raise SystemExit(asyncio.run(main(parser.parse_args())))
