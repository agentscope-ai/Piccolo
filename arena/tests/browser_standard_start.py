"""Real frontend + local native API; standard/seeded resets without model calls.

Run from the source root with PYTHONPATH=. and --output <artifact directory>.
"""
import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from blink_arena.app import create_app
from blink_arena.schemas import AppConfig


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    assets = Path(__file__).resolve().parents[1] / 'web'
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(assets)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    calls, errors, results = [], [], []
    try:
        with tempfile.TemporaryDirectory() as folder, TestClient(create_app(data=folder, config=AppConfig())) as client, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page(viewport={'width':1440, 'height':1100}, reduced_motion='reduce')
            page.on('pageerror', lambda e: errors.append(str(e)))

            def route(route):
                req = route.request
                u = urlparse(req.url)
                response = client.request(req.method, u.path + ('?' + u.query if u.query else ''),
                                          content=req.post_data, headers={'content-type':'application/json'})
                if req.method == 'POST' and u.path in ('/api/game/new', '/api/showcases/new', '/api/v1/sessions'):
                    calls.append({'path':u.path, 'body':json.loads(req.post_data), 'response':response.json()})
                # A stale server catalog must not resurrect a removed game.
                if u.path == '/api/showcases':
                    data = response.json()
                    data.append({'kind':'iterated_rps', 'name':'Retired RPS', 'mode':'game', 'featured':True})
                    route.fulfill(status=200, json=data)
                else:
                    route.fulfill(status=response.status_code, content_type=response.headers.get('content-type','application/json'), body=response.content)

            page.route('**/api/**', route)
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            page.wait_for_function('typeof showcaseKinds!=="undefined"&&showcaseKinds.length>0&&catalog&&!busy')
            page.locator('[data-tab="games"]').click()
            page.wait_for_function('showcaseSession?.world.kind==="snake_navigation"&&!showcaseBusy')
            assert calls[-1]['body']['kind'] == 'snake_navigation' and 'seed' not in calls[-1]['body']
            assert calls[-1]['response']['world']['steps'] == 0
            assert page.locator('#gamePicker .active').get_attribute('data-kind') == 'snake_navigation'
            initial_session = page.evaluate('showcaseSession.session_id')
            page.locator('[data-tab="blog"]').click()
            page.locator('[data-tab="games"]').click()
            assert page.evaluate('showcaseSession.session_id') == initial_session
            assert page.evaluate('gameState') is None
            featured = ['snake_navigation','sokoban_puzzle','blackjack','chess','tetris_placement','uno']
            assert page.locator('#gamePicker [data-kind]').evaluate_all('(ns)=>ns.map(n=>n.dataset.kind)') == featured
            page.locator('#playBrowseGames').click()
            page.locator('#playFilters [data-filter="all"]').click()
            assert page.locator('#gamePicker [data-kind="iterated_rps"]').count() == 0
            kinds = page.locator('#gamePicker [data-kind]').evaluate_all('(ns)=>ns.map(n=>n.dataset.kind)')
            page.locator('.play-library-close').click()

            def settle():
                page.wait_for_function('!busy&&!showcaseBusy')
                assert page.locator('#globalError').evaluate('n=>n.classList.contains("hidden")'), page.locator('#globalError').inner_text()

            def standard_request():
                body = calls[-1]['body']
                assert body.get('seed') == 0 if body.get('game') == 'chess' else 'seed' not in body, body
                response = calls[-1]['response']
                world = response.get('world', response.get('state', {}))
                assert world.get('steps', 0) == 0, (body, world.get('steps'))
                if body.get('game') == 'chess':
                    assert world['opening_plies'] == 0 and len(world['moves_uci']) == 0
                assert page.locator('#playSeedStatus').inner_text() in ('Standard start', '标准开局')

            def workspace_layout(content, *, seed_visible=True):
                scene = page.locator(content)
                assert scene.is_visible()
                assert page.locator('#playWorkspaceBar').is_visible()
                assert not page.locator('#playLibrary').is_visible()
                bar = page.locator('#playWorkspaceBar').bounding_box()
                assert bar['y'] + bar['height'] <= scene.bounding_box()['y'] + 1
                if seed_visible:
                    seed = page.locator('#playSeedTools')
                    assert seed.is_visible()
                    assert seed.evaluate('n=>n.parentElement.classList.contains("play-aside")')
                    surface = scene.locator('.play-main,.board-wrap').first.bounding_box()
                    assert seed.bounding_box()['x'] >= surface['x'] + surface['width'] - 1
                else:
                    assert not page.locator('#playSeedTools').is_visible()

            for kind in kinds:
                page.locator('#playQuickGame').select_option(kind)
                settle()
                if kind == 'mbti_text':
                    workspace_layout('#mbtiPlay', seed_visible=False)
                    results.append({'kind':kind, 'compact_game_switcher':True, 'seed_hidden':True})
                    continue
                is_board = page.locator('#boardPlay').is_visible()
                is_world = kind in ('mario_platformer', 'terraria_survival')
                content = '#boardPlay' if is_board else '#showcasesView'
                workspace_layout(content)
                if not is_world:
                    standard_request()
                else:
                    page.evaluate('''()=>{const bridge=worldBridge(),reset=bridge.reset;window.resetSnapshots=[];bridge.reset=function(...args){const obs=reset.apply(this,args);resetSnapshots.push({args,obs});return obs;}}''')
                page.locator('#playSeed').fill('42')
                page.locator('#playSeedApply').click()
                settle()
                if not is_world:
                    assert calls[-1]['body']['seed'] == 42
                else:
                    assert page.evaluate('resetSnapshots.at(-1).args[0]') == 42
                assert '42' in page.locator('#playSeedStatus').inner_text()
                # Ignore an invalid unused seed draft on an ordinary restart.
                page.locator('#playSeed').fill('invalid')
                page.locator('#newGame' if is_board else '#showcaseNew').click()
                settle()
                if not is_world:
                    standard_request()
                else:
                    snapshot = page.evaluate('resetSnapshots.at(-1)')
                    assert snapshot['args'] == [None]
                    assert snapshot['obs']['decisions'] == 0
                    assert page.locator('#playSeedStatus').inner_text() in ('Standard start', '标准开局')
                results.append({'kind':kind, 'standard_default':True, 'explicit_seed':True, 'restart_standard':True, 'compact_game_switcher':True, 'seed_beside_content':True})
                print(kind, 'PASS', flush=True)
            page.locator('#playQuickGame').select_option('chess')
            settle()
            # Change the position, then use the normal restart control.
            page.evaluate("()=>JevChessUI.step('e2e4',false)")
            settle()
            assert page.evaluate('showcaseSession.world.steps') > 0
            page.locator('#showcaseNew').click()
            settle()
            standard_request()
            page.locator('#playBrowseGames').click()
            page.locator('#playSearch').fill('')
            page.locator('#playFilters [data-filter="new"]').click()
            page.locator('.play-library-close').click()
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(args.output/'desktop.png'), full_page=True)
            page.set_viewport_size({'width':390, 'height':844})
            page.wait_for_timeout(200)
            page.screenshot(path=str(args.output/'mobile.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), page.evaluate('''()=>[...document.querySelectorAll('#gamesView *')].map(n=>({id:n.id,cls:n.className,right:n.getBoundingClientRect().right,width:n.getBoundingClientRect().width})).filter(n=>n.right>innerWidth+1).slice(0,12)''')
            assert not errors, errors
            (args.output/'report.json').write_text(json.dumps({'passed':True, 'games':results, 'page_errors':errors}, indent=2))
            browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
