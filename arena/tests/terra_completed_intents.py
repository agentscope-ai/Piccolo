"""Compare public candidate completion with the unchanged real JS executor."""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from playwright.async_api import async_playwright
from terra_core_test_support import engine_source, test_source, install_fixture

PACKAGE = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


async def run(args):
    package = args.package.resolve()
    sys.path.insert(0, str(package))
    import blink_arena
    import jev_terraria_contract as contract
    assert Path(contract.__file__).resolve().is_relative_to(package)
    source = engine_source(package)
    original = test_source(source)
    marker = "var eg=combat?Object.assign({},enemy,enemy.geometry||{}):enemy,ex=eg.x+eg.width/2-(p.x+p.width/2),ey=eg.y+eg.height/2-(p.y+p.height/2),gap=Math.max(0,Math.abs(ex)-(eg.width+p.width)/2);"
    assert original.count(marker) == 1
    # Read-only instrumentation captures exactly the public state used by B.
    observed = original.replace(marker, "if(window.__motionFrames)window.__motionFrames.push({observation:structuredClone(obs),target:structuredClone(enemy),retreat:p.x+p.width<enemy.x-7,pass:p.x>enemy.x+enemy.width+8});" + marker)
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(package / 'web')))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cases = [
        ('retreat_done', 'retreat_left', 10., [18.]),
        ('retreat_equal', 'retreat_left', 10.375, [18.]),
        ('retreat_strict_below', 'retreat_left', 10.374, [18.]),
        ('retreat_strict_above', 'retreat_left', 10.376, [18.]),
        ('pass_done', 'pass_enemy_right', 10., [1.]),
        ('pass_equal', 'pass_enemy_right', 9.875, [1.]),
        ('pass_strict_below', 'pass_enemy_right', 9.874, [1.]),
        ('pass_strict_above', 'pass_enemy_right', 9.876, [1.]),
        ('retreat_enemy_behind', 'retreat_left', 10., [8.]),
        ('pass_enemy_ahead', 'pass_enemy_right', 10., [12.]),
        ('nearest_exact_geometry', 'retreat_left', 10.04, [9.1, 10.9]),
        ('nearest_tied_distance', 'retreat_left', 10., [9., 11.]),
    ]
    rows, checks = [], {}
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await install_fixture(page, package);await page.add_init_script('window.__JEV_TEST_MODE__=true;window.__motionFrames=[];')
                async def intercept(route):
                    await route.fulfill(status=200, content_type='application/javascript', body=observed)
                await page.route('**/'+engine_source(package).name+'*', intercept)
                await page.goto(f'http://127.0.0.1:{server.server_port}/playground/terraria.html')
                for name, action, x, enemy_xs in cases:
                    row = await page.evaluate('''async ({action,x,enemy_xs})=>{
                      const api=JevTerramai;api.reset(20261017);
                      api.fixture({x,y:13.75,dirt:0,tiles:Array.from({length:48},(_,i)=>[i,15,2]),
                        enemies:enemy_xs.map(ex=>({kind:'slime',x:ex*16,y:13.75*16,w:14,h:20,hp:500,maxhp:500,lv:1,vx:0,vy:0,t:0,ground:true}))});
                      api.activate(true);const before=structuredClone(api.prepare({clock:'step'}));
                      window.__motionFrames=[];const after=structuredClone(await api.act(action));
                      api.activate(false);return {before,after,first:window.__motionFrames[0],render_error:window.jevRenderError||null};
                    }''', {'action': action, 'x': x, 'enemy_xs': enemy_xs})
                    first = row['first'];obs = first['observation']
                    facts = contract.enemy_motion_facts(obs)
                    record = contract.as_record(obs);options = record['questions']['decision']['criteria']
                    completed = first['retreat' if action == 'retreat_left' else 'pass']
                    row.update(name=name, action=action, candidate_facts=facts)
                    local = {
                        'target_matches_executor': facts['target'] == first['target'],
                        'retreat_predicate_matches_executor': facts['retreat_left']['already_satisfied'] == first['retreat'],
                        'pass_predicate_matches_executor': facts['pass_enemy_right']['already_satisfied'] == first['pass'],
                        'omission_only_when_current_completion_exact': (action not in options) == completed,
                        'recover_preserved': 'recover' in options,
                        'fight_preserved': 'fight_nearest' in options,
                        'single_choice': list(record['questions']) == ['decision'],
                        'C0': row['after']['execution_audit']['rule_takeover_count'] == 0,
                        'one_model_decision': row['after']['execution_audit']['model_decisions'] == 1,
                        'no_render_error': not row['render_error'],
                    }
                    if completed:
                        effect = row['after']['control']['recent_effects'][-1]
                        local.update(original_executor_one_frame=effect['frames'] == 1,
                                     original_executor_completed=effect['event'] == 'target_completed',
                                     current_mechanical_horizontal_zero=effect['delta_x'] == 0,
                                     disclosed_zero=facts[action]['controlled_horizontal_displacement_if_state_unchanged'] == 0)
                    if name.endswith('equal'):
                        local['strict_equality_is_not_completion'] = not completed
                    if name == 'nearest_exact_geometry':
                        local['exact_coordinate_breaks_rounded_tie'] = first['target']['x'] == 10.9
                    if name == 'nearest_tied_distance':
                        local['id_breaks_tie'] = first['target']['id'] == min(e['id'] for e in obs['enemies'])
                    row['checks'] = local
                    checks.update({name + ':' + key: value for key, value in local.items()})
                    rows.append(row)
                await page.close()
            finally:
                await browser.close()
    finally:
        await asyncio.to_thread(server.shutdown)
        server.server_close();thread.join(timeout=2)
    assert test_source(source) == original
    base = deepcopy(rows[0]['first']['observation'])
    base['player'].pop('geometry')
    legacy = contract.as_record(base)
    checks['rounded_legacy_not_filtered_as_exact'] = 'retreat_left' in legacy['questions']['decision']['criteria']
    base['enemies'] = []
    empty = contract.as_record(base)
    checks['no_enemy_no_enemy_actions'] = not any(a in empty['questions']['decision']['criteria'] for a in ('fight_nearest', 'retreat_left', 'pass_enemy_right'))
    checks['no_enemy_recover_preserved'] = 'recover' in empty['questions']['decision']['criteria']
    result = {'passed': all(checks.values()), 'checks': checks, 'cases': len(rows), 'real_chromium': True,
              'model_calls': 0, 'GPU_calls': 0, 'executor_source_unchanged': True, 'rows': rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'passed': result['passed'], 'cases': len(rows), 'checks': len(checks),
                      'failed': [k for k,v in checks.items() if not v]}), flush=True)
    return int(not result['passed'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, default=PACKAGE)
    parser.add_argument('--out', type=Path, required=True)
    raise SystemExit(asyncio.run(run(parser.parse_args())))
