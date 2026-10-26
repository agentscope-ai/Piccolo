"""Chess UI against the actual native session service, with explicit CPU fixtures.

No real model/API calls, GPU use, public deployment or leaderboard writes.
Promotion/endgame FENs are installed directly in this disposable test app only.
"""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from blink_arena.app import create_app
from blink_arena.schemas import AppConfig, DecisionOutput
import jev_chess

OUT = Path(os.environ.get('JEV_CHESS_TEST_OUT', Path(tempfile.gettempdir()) / 'jev-chess-browser'))
MODEL = 'chess-frontend-fixture'


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assets = Path(__file__).resolve().parents[1] / 'web'
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(assets)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checks, calls, requests, errors = [], [], [], []
    try:
        with tempfile.TemporaryDirectory() as folder, TestClient(create_app(data=folder, config=AppConfig())) as client, sync_playwright() as pw:
            response = client.post('/api/v1/connections', json={'model_id': MODEL, 'name': 'Chess CPU fixture',
                                   'served_model': MODEL, 'adapter': 'decision', 'transport': 'browser'})
            assert response.status_code == 201, response.status_code

            async def fixture(request):
                calls.append({'game': request.game, 'option_count': len(request.question.options)})
                options = request.question.options
                return DecisionOutput(request_id=request.request_id, model=request.model, action=options[0].id,
                                      probabilities={o.id: 1 / len(options) for o in options})

            client.app.state.providers.browser_relays[MODEL] = fixture
            client.app.state.connections.entries[MODEL]['last_poll'] = time.monotonic()
            browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1400, 'height': 1100})
            page.on('pageerror', lambda e: errors.append(str(e)))

            def route(route):
                req = route.request
                parsed = urlparse(req.url)
                headers = {'content-type': 'application/json', 'X-Demo-Model': MODEL}
                data = json.loads(req.post_data) if req.post_data and req.headers.get('content-type', '').startswith('application/json') else None
                if parsed.path.startswith('/api/v1/sessions'):
                    requests.append({'path': parsed.path, 'method': req.method, 'body': data})
                result = client.request(req.method, parsed.path + ('?' + parsed.query if parsed.query else ''), content=req.post_data, headers=headers)
                route.fulfill(status=result.status_code, content_type=result.headers.get('content-type', 'application/json'), body=result.content)

            page.route('**/api/**', route)
            page.goto(f'http://127.0.0.1:{server.server_port}/?model={MODEL}')
            page.wait_for_function('modelReady && typeof showcaseKinds!=="undefined" && showcaseKinds.some(g=>g.kind==="chess") && !busy')
            page.locator('[data-tab="games"]').click()
            page.wait_for_function('showcaseSession?.world.kind==="snake_navigation"&&!showcaseBusy')
            page.locator('#playSeed').fill('0')
            page.locator('#playSearch').fill('chess')
            page.locator('#gamePicker [data-kind="chess"]').click()
            page.wait_for_function('showcaseSession?.world.kind==="chess" && !showcaseBusy')
            assert page.locator('#chessStage').is_visible()
            assert page.locator('.jev-chess-square').count() == 64
            assert page.locator('.jev-chess-piece').count() == 32
            assert not page.locator('#showcaseCanvas').is_visible()
            assert not page.locator('#agentGameStage').is_visible()
            assert page.locator('[data-square="e1"]').get_attribute('aria-label').endswith('White King')
            checks.append('native_session_standard_board')

            def quiet():
                page.wait_for_function('!showcaseBusy')
                assert not errors, errors
                assert page.locator('#globalError').evaluate('n=>n.classList.contains("hidden")'), page.locator('#globalError').inner_text()

            def move(uci):
                previous = page.evaluate('showcaseSession.world.steps')
                page.locator(f'[data-square="{uci[:2]}"]').click()
                assert page.locator(f'[data-square="{uci[2:4]}"]').evaluate('n=>n.classList.contains("legal")')
                page.locator(f'[data-square="{uci[2:4]}"]').click()
                if len(uci) == 5:
                    assert page.evaluate('showcaseSession.world.steps') == previous
                    page.locator(f'[data-promotion="{uci[4]}"]').click()
                page.wait_for_function('n=>!showcaseBusy&&showcaseSession.world.steps===n+1', arg=previous)
                quiet()

            page.locator('[data-square="e2"]').click()
            assert page.locator('[data-square="e4"]').evaluate('n=>n.classList.contains("legal")')
            assert not page.locator('[data-square="e5"]').evaluate('n=>n.classList.contains("legal")')
            page.locator('[data-square="e5"]').click()
            assert page.evaluate('showcaseSession.world.steps') == 0
            move('e2e4')
            assert page.locator('.jev-chess-status').inner_text().startswith('Black')
            checks.append('legal_uci_origin_destination_and_illegal_click')

            page.locator('#chessSeatStep').click()
            page.wait_for_function('!showcaseBusy&&showcaseSession.world.steps===2')
            assert page.evaluate('showcaseSession.world.controller_counts.rule_opponent_moves') == 1
            assert page.evaluate('showcaseSession.world.history.at(-1).controller') == 'rule_engine'
            assert 'Rule engine' in page.locator('#showcaseResult').inner_text()
            checks.append('rule_black_seat_explicit_attribution')

            before = page.evaluate('structuredClone(showcaseSession.input)')
            page.locator('#showcaseModel').click()
            page.wait_for_function('!showcaseBusy&&showcaseSession.world.steps===3')
            quiet()
            assert page.evaluate('showcaseSession.world.history.at(-1).controller') == 'model'
            assert page.locator('#showcaseResult [data-i18n-result]').count() == 1
            assert '%' in page.locator('#showcaseResult').inner_text()
            assert before['state']['observation']['fen'] in page.locator('#showcaseFields').text_content(), {
                'expected_public_fen':before['state']['observation']['fen'],
                'display_prefix':page.locator('#showcaseFields').text_content()[:500]}
            assert page.evaluate('showcaseSession.input.state.observation.fen') != before['state']['observation']['fen']
            checks.append('model_probabilities_and_exact_previous_input')

            page.locator('#chessSeat-black').select_option('human')
            page.locator('.jev-chess-flip').click()
            assert page.locator('.jev-chess-square').first.get_attribute('data-square') == 'h1'
            assert not page.locator('[data-square="a7"]').is_disabled()
            page.locator('.jev-chess-flip').click()
            checks.append('black_human_seat_and_board_orientation')

            # The configured next side is used by autoplay, with a pause at human turns.
            page.locator('#chessSeat-white').select_option('rule')
            page.locator('#showcaseAuto').click()
            current = page.evaluate('showcaseSession.world.steps')
            page.wait_for_timeout(350)
            assert page.evaluate('showcaseSession.world.steps') == current
            page.locator('#chessSeat-black').select_option('model')
            page.wait_for_function('n=>showcaseSession.world.steps>n', arg=current)
            page.evaluate('stopAuto()')
            quiet()
            checks.append('configured_model_and_rule_seats_autoplay_pause_at_human')

            def setup(fen, max_plies=320):
                page.evaluate('stopAuto()')
                quiet()
                ident = page.evaluate('showcaseSession.session_id')
                sessions = client.app.state.sessions
                sessions.items[ident]['world'] = jev_chess.fresh(0, fen=fen, max_plies=max_plies)
                sessions.items[ident]['revision'] += 1
                # Load the fixture through the same fresh-session HTTP response as production.
                fixture_state = client.get('/api/v1/sessions/' + ident).json()
                def fixture_create(route):
                    route.fulfill(status=201, content_type='application/json', body=json.dumps(fixture_state))
                page.route('**/api/v1/sessions', fixture_create, times=1)
                page.evaluate('newShowcase()')
                quiet()
                page.locator('#chessSeat-white').select_option('human')
                page.locator('#chessSeat-black').select_option('human')
                return ident

            setup('7k/P7/8/8/8/8/8/7K w - - 0 1')
            page.locator('[data-square="a7"]').click()
            page.locator('[data-square="a8"]').click()
            assert page.locator('[data-promotion]').count() == 4
            assert page.evaluate('showcaseSession.world.steps') == 0
            page.locator('[data-promotion="n"]').click()
            page.wait_for_function('!showcaseBusy&&showcaseSession.world.steps===1')
            quiet()
            assert page.evaluate('showcaseSession.world.board[0][0]') == 'N'
            checks.append('four_explicit_promotion_choices_underpromotion')

            setup('7k/6Q1/6K1/8/8/8/8/8 b - - 0 1')
            assert 'Checkmate' in page.locator('.jev-chess-status').inner_text()
            assert 'White' in page.locator('.jev-chess-status').inner_text()
            assert page.locator('#showcaseModel').is_disabled()
            assert page.locator('.jev-chess-square:disabled').count() == 64
            checks.append('checkmate_winner_and_terminal_controls')

            setup('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1')
            assert 'Stalemate' in page.locator('.jev-chess-status').inner_text()
            assert 'Draw' in page.locator('.jev-chess-status').inner_text()
            checks.append('stalemate_not_a_win')

            setup('7k/8/8/8/8/8/8/R6K w - - 100 1')
            assert page.locator('#showcaseActions [data-action^="claim_draw:"]').count() > 0
            page.locator('#showcaseActions [data-action^="claim_draw:"]').first.click()
            page.wait_for_function('!showcaseBusy&&!!showcaseSession.world.outcome')
            quiet()
            assert 'Draw' in page.locator('.jev-chess-status').inner_text()
            checks.append('explicit_legal_draw_claim')

            setup('7k/8/8/8/8/8/8/R6K w - - 0 1', max_plies=1)
            move('a1a2')
            assert 'Unfinished' in page.locator('.jev-chess-status').inner_text()
            assert 'Draw' not in page.locator('.jev-chess-status').inner_text()
            checks.append('budget_exhaustion_not_draw_or_win')

            # New seeds really replace the native board and remove only old UI sessions.
            page.locator('#playSeed').fill('42')
            page.locator('#playSeedApply').click()
            page.wait_for_function('!showcaseBusy&&showcaseSession.environment.seed===42')
            seed42 = page.evaluate('showcaseSession.world.fen')
            page.locator('#playSeed').fill('43')
            page.locator('#playSeedApply').click()
            page.wait_for_function('!showcaseBusy&&showcaseSession.environment.seed===43')
            assert seed42 != page.evaluate('showcaseSession.world.fen')
            checks.append('seed_changes_public_opening')

            page.evaluate('activatePlay(false)')
            assert not page.locator('#chessStage').is_visible()
            page.evaluate('activatePlay(true)')
            assert page.locator('#chessStage').is_visible()
            checks.append('tab_hide_restore_and_autoplay_stop')

            page.locator('[data-language="zh"]').click()
            assert '白方' in page.locator('.jev-chess-status').inner_text()
            assert '人类' in page.locator('#chessSeat-white option:checked').inner_text()
            checks.append('chinese_language_redraw')
            page.screenshot(path=str(OUT / 'chess-desktop.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 900})
            assert page.locator('.jev-chess-board').evaluate('n=>n.getBoundingClientRect().width<=window.innerWidth')
            page.locator('#chessStage').screenshot(path=str(OUT / 'chess-mobile.png'))
            checks.append('mobile_responsive_board')

            page.set_viewport_size({'width': 1400, 'height': 1100})
            for kind in ('sokoban_puzzle', 'checkers'):
                page.locator('#playSearch').fill(kind)
                page.locator(f'#gamePicker [data-kind="{kind}"]').click()
                page.wait_for_function('k=>showcaseSession?.world.kind===k&&!showcaseBusy', arg=kind)
                assert not page.locator('#chessStage').is_visible()
                if kind == 'checkers':
                    assert page.locator('#selectedGameBoard').is_visible()
                quiet()
            checks.append('existing_sokoban_selected_renderer_switch_preserved')
            browser.close()
        result = {'passed': True, 'checks': checks, 'check_count': len(checks), 'fixture_prediction_calls': len(calls),
                  'real_model_calls': 0, 'page_errors': errors, 'native_session_http_requests': len(requests),
                  'gpu_used': False, 'public_deployment': False}
        (OUT / 'frontend-browser-regression.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    main()
