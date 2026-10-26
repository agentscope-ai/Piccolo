"""Exercise approval-boundary behavior using a local fake decision service."""
import json
from pathlib import Path
import subprocess
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/blink-safety-review/scripts'
sys.path.insert(0, str(SCRIPTS))
import review_action as review
from download_model import download_plan
import download_model

ACTION = {'user_request': 'Read README.md', 'authorized_scope': 'Read this file only',
          'tool_name': 'read_file', 'arguments': {'file_path': 'README.md'}}
REQUEST = review.build_request(ACTION, 'fixture-model', 'request-1')


def response(**updates):
    return {'schema_version': 'jev.decision.v1', 'request_id': 'request-1', 'model': 'fixture-model',
            'action': 'allow', 'probabilities': {'allow': .99, 'ask_user': .005, 'deny': .005}, **updates}


def test_allow_needs_configured_threshold_and_full_matching_distribution():
    assert review.parse_response(response(), REQUEST, None)['decision'] == 'ask_user'
    assert review.parse_response(response(), REQUEST, .995)['decision'] == 'ask_user'
    assert review.parse_response(response(), REQUEST, .98)['decision'] == 'allow'


@pytest.mark.parametrize('updates', [
    {'model': 'other-model'}, {'request_id': 'other-request'}, {'schema_version': 'unknown'},
    {'probabilities': {'allow': 1}}, {'probabilities': None},
    {'probabilities': {'allow': True, 'ask_user': 0, 'deny': 0}},
    {'probabilities': {'allow': float('nan'), 'ask_user': 0, 'deny': 0}},
    {'probabilities': {'allow': .99, 'ask_user': .3, 'deny': .2}},
    {'action': 'allow', 'probabilities': {'allow': .1, 'ask_user': .2, 'deny': .7}},
])
def test_invalid_or_mismatched_response_never_allows(updates):
    assert review.parse_response(response(**updates), REQUEST, .98)['decision'] == 'ask_user'


def test_deny_and_ask_user_are_preserved():
    for action in ('deny', 'ask_user'):
        probs = {key: float(key == action) for key in review.DECISIONS}
        assert review.parse_response(response(action=action, probabilities=probs), REQUEST, .98)['decision'] == action


@pytest.mark.parametrize('endpoint', ['https://example.com/decision', 'http://user:secret@127.0.0.1/review',
                                     'http://localhost/decision', 'http://127.0.0.1/decision?key=secret'])
def test_nonlocal_or_credential_endpoints_are_rejected(endpoint):
    result = review.review(ACTION, endpoint=endpoint, model='fixture-model', threshold=.98)
    assert result['decision'] == 'ask_user'
    assert 'secret' not in json.dumps(result)


def test_missing_real_authorization_is_not_invented():
    with pytest.raises(ValueError):
        review.build_request({**ACTION, 'authorized_scope': ''}, 'fixture-model', 'r')


@pytest.mark.parametrize('data', ['{"action":"deny","action":"allow"}', '{"allow":NaN}', '{"allow":Infinity}'])
def test_ambiguous_json_is_rejected(data):
    with pytest.raises(ValueError):
        review.strict_json(data)


def test_local_service_roundtrip_and_outage():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body)
            result = response(request_id=body['request_id'], model=body['model'])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    endpoint = f'http://127.0.0.1:{server.server_port}/decision'
    try:
        result = review.review(ACTION, endpoint=endpoint, model='fixture-model', threshold=.98)
        assert result['decision'] == 'allow'
        assert result['executes_action'] is False
        assert requests[0]['observation'] == ACTION
        assert {o['id'] for o in requests[0]['question']['options']} == review.DECISIONS
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    assert review.review(ACTION, endpoint=endpoint, model='fixture-model', threshold=.98, timeout=.1)['decision'] == 'ask_user'


def test_unpublished_release_never_downloads_or_reviews(tmp_path):
    release = json.loads((SCRIPTS.parent / 'assets/release.json').read_text())
    with pytest.raises(ValueError):
        download_plan(release, tmp_path / 'weights')
    proc = subprocess.run([sys.executable, str(SCRIPTS / 'download_model.py'), '--output', str(tmp_path / 'weights'), '--dry-run'], capture_output=True, text=True)
    assert proc.returncode == 2
    assert not (tmp_path / 'weights').exists()
    proc = subprocess.run([sys.executable, str(SCRIPTS / 'review_action.py'), '--input', str(SCRIPTS.parent / 'assets/action.example.json')], capture_output=True, text=True)
    assert proc.returncode == 2
    assert json.loads(proc.stdout)['reason'] == 'model_release_not_configured'


def test_download_requires_explicit_repo_revision_and_file_scope(tmp_path):
    release = {'schema_version': 'blink.safety.release.v1', 'status': 'released', 'provider': 'huggingface',
               'repo_id': 'fixture/blink', 'revision': 'v1.0', 'allow_patterns': ['*.safetensors', '*.json']}
    assert download_plan(release, tmp_path)['revision'] == 'v1.0'
    for key, value in [('revision', 'main'), ('repo_id', None), ('allow_patterns', [])]:
        with pytest.raises(ValueError):
            download_plan({**release, key: value}, tmp_path)


@pytest.mark.parametrize('payload', [True, False])
def test_download_receipt_is_complete_only_after_payload_arrives(tmp_path, monkeypatch, capsys, payload):
    release = {'schema_version': 'blink.safety.release.v1', 'status': 'released', 'provider': 'huggingface',
               'repo_id': 'fixture/blink', 'revision': 'v1.0', 'allow_patterns': ['*.safetensors']}
    config = tmp_path / 'release.json'
    config.write_text(json.dumps(release))
    output = tmp_path / 'model'
    calls = []

    def snapshot_download(**kwargs):
        calls.append(kwargs)
        if payload:
            (Path(kwargs['local_dir']) / 'fixture.safetensors').write_bytes(b'test fixture; not a model')

    monkeypatch.setitem(sys.modules, 'huggingface_hub', types.SimpleNamespace(snapshot_download=snapshot_download))
    monkeypatch.setattr(sys, 'argv', ['download_model.py', '--release', str(config), '--output', str(output)])
    assert download_model.main() == (0 if payload else 2)
    assert len(calls) == 1 and calls[0]['revision'] == 'v1.0'
    assert json.loads((output / 'blink-download.json').read_text())['complete'] is payload
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == ('downloaded' if payload else 'download_failed')
