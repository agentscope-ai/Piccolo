"""Local-only browser QA factory; never imported by the production entrypoint."""
import json
import os
import tempfile
from pathlib import Path

import httpx
from blink_arena.app import create_app


def create():
    os.environ['DASHSCOPE_API_KEY'] = 'fixture-local-not-a-real-key'
    root = Path(tempfile.mkdtemp(prefix='jev-hosted-qa-'))
    app = create_app(data=root, seed=root/'missing')

    async def respond(request):
        if request.url.host == 'dashscope.aliyuncs.com':
            return httpx.Response(200, json={'token': 'fixture-temporary-token'})
        body = json.loads(request.content)
        qid, question = next(iter(body['input']['questions'].items()))
        options = question['option_order']
        action = next((v for v in ('right','jump_right','call','check','roll','next','skip','hit') if v in options),options[0])
        return httpx.Response(200,json={'output': {'model': 'jev-1026', 'answers': {qid: {
            'type':'choice','choice':action,'probabilities':{k:float(k==action) for k in options}}}},
            'usage':{'input_tokens':100,'output_tokens':1}})

    app.state.hosted_model.http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    return app
