"""Request question list -> complete body -> ordered images -> identical body.

Image resizing follows decision_index.vision (see licenses/Decision-Index-MIT.txt).
"""
import asyncio
import base64
import hashlib
import io
import json
import math

from fastapi import Request
from starlette.responses import JSONResponse
from PIL import Image
from sglang.srt.managers.io_struct import GenerateReqInput
from transformers import AutoTokenizer

MAX_PIXELS = 1638400
LETTERS = 'ABCDEFGHIJKL'
TAIL = "Answer with the option's letter from the given choices directly."
VISION_FORMAT = 'question_list_text_images_text'
PROMPT_REVISION = '20261030'


def image_url(ref):
    """Accept data URLs or base64 from the HTTP client; cap before processing."""
    raw = base64.b64decode(ref.split(',', 1)[1] if ref.startswith('data:') else ref, validate=True)
    with Image.open(io.BytesIO(raw)) as image:
        width, height = image.size
        fmt = image.format
        if width * height > MAX_PIXELS:
            scale = (MAX_PIXELS / (width * height)) ** 0.5
            width, height = max(1, int(width * scale)), max(1, int(height * scale))
            fmt = 'PNG' if fmt == 'PNG' else 'JPEG'
            mode = 'RGBA' if fmt == 'PNG' and ('A' in image.mode or 'transparency' in image.info) else 'RGB'
            resized = image.convert(mode).resize((width, height), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            resized.save(buffer, format=fmt, **({'quality': 95} if fmt == 'JPEG' else {}))
            raw = buffer.getvalue()
        elif fmt not in ('PNG', 'JPEG', 'WEBP', 'GIF'):
            buffer = io.BytesIO()
            image.convert('RGB').save(buffer, format='JPEG', quality=95)
            raw, fmt = buffer.getvalue(), 'JPEG'
    return f'data:image/{fmt.lower()};base64,' + base64.b64encode(raw).decode(), width * height


def conversations(state, questions, images, prompt, max_images=4):
    if not isinstance(questions, dict) or not questions:
        raise ValueError('questions must be a nonempty mapping')
    texts = []
    for key, question in questions.items():
        if not isinstance(key, str) or not isinstance(question, dict):
            raise ValueError('Question IDs must be strings and questions must be objects')
        if question['type'] != 'choice':
            raise ValueError('vision requests take choice questions only')
        keys = list(question['criteria'])
        if not 2 <= len(keys) <= len(LETTERS) or keys != list(LETTERS[:len(keys)]):
            raise ValueError('options per choice: vision requires 2..12 consecutive keys A, B, C, ...')
        text = question['instructions']
        texts.append(text if isinstance(text, str) else json.dumps(text, ensure_ascii=False))
    header = 'Questions that will be asked about the context:\n' + '\n'.join('- '+t for t in texts) + '\n\n'
    if not isinstance(images, list) or not 1 <= len(images) <= max_images:
        raise ValueError(f'the canvas holds 1..{max_images} images per request')
    prompt = {} if prompt is None else prompt
    if not isinstance(prompt, dict) or set(prompt) - {'readout', 'options_in_image'}:
        raise ValueError('prompt accepts only readout and options_in_image')
    readout = prompt.get('readout')
    if readout is not None and not isinstance(readout, str):
        raise ValueError('readout must be a string or null')
    if 'options_in_image' in prompt and type(prompt['options_in_image']) is not bool:
        raise ValueError('options_in_image must be boolean')
    urls, pixels, hashes = [], [], []
    for ref in images:
        url, count = image_url(ref)
        urls.append(url)
        pixels.append(count)
        hashes.append(hashlib.sha256(base64.b64decode(url.split(',', 1)[1])).hexdigest())
    metadata = dict(image_pixels=pixels, image_sha256=hashes,
        image_order=list(range(1, len(images)+1)), readout=readout,
        options_in_image=bool(prompt.get('options_in_image')), vision_format=VISION_FORMAT,
        prompt_revision=PROMPT_REVISION, question_list_prefix=True,
        question_count=len(questions), body_copies=2,
        header_sha256=hashlib.sha256(header.encode()).hexdigest())
    rows = []
    for key, question in questions.items():
        if prompt.get('options_in_image'):
            body = f"{question['instructions']} {TAIL}"
        else:
            options = '\n'.join(f'{k}. {v}' for k, v in question['criteria'].items())
            body = f"{question['instructions']}\n{options}\n{TAIL}"
        if state not in (None, {}, ''):
            context = state if isinstance(state, str) else json.dumps(state, ensure_ascii=False, separators=(',', ':'))
            body = 'State:\n' + context + '\n\n' + body
        content = [dict(type='text', text=header), dict(type='text', text=body)]
        content.extend(dict(type='image_url', image_url=dict(url=url)) for url in urls)
        content.append(dict(type='text', text=body))
        messages = [dict(role='user', content=content)]
        if readout:
            messages.append(dict(role='assistant', content=readout))
        rows.append((key, list(question['criteria']), messages,
                     hashlib.sha256(body.encode()).hexdigest()))
    return rows, urls, metadata


class Vision:
    def __init__(self, model, tokenizer_path):
        self.model = model
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
        self.label_ids = [self.tokenizer.encode(c, add_special_tokens=False) for c in LETTERS]
        if any(len(ids) != 1 for ids in self.label_ids):
            raise ValueError('Vision option labels must be single tokens')
        self.label_ids = [ids[0] for ids in self.label_ids]
        self.image_token_id = self.tokenizer.convert_tokens_to_ids('<|image_pad|>')
        self.lock = asyncio.Lock()

    async def handle(self, request: Request):
        try:
            body = await request.json()
            async with self.lock:
                return JSONResponse(await self.infer(body, request))
        except (ValueError, KeyError, TypeError) as error:
            return JSONResponse({'error': str(error)}, status_code=422)
        except (RuntimeError, OSError) as error:
            return JSONResponse({'error': str(error)}, status_code=502)

    async def infer(self, body, request):
        from sglang.srt.entrypoints.http_server import get_global_state
        manager = get_global_state().tokenizer_manager

        if body.get('model', self.model) != self.model:
            raise ValueError('model must match the served model')
        rows, images, metadata = await asyncio.to_thread(
            conversations, body['state'], body['questions'], body['images'], body.get('prompt'))
        answers, readouts = {}, {}
        usage = dict(input_tokens=0, output_tokens=0, cached_tokens=0)
        for key, keys, messages, body_hash in rows:
            text = self.tokenizer.apply_chat_template(messages, tokenize=False,
                enable_thinking=False, add_generation_prompt=not bool(metadata['readout']),
                continue_final_message=bool(metadata['readout']))
            candidate_ids = self.label_ids[:len(keys)]
            obj = GenerateReqInput(
                text=text, image_data=images, return_prompt_token_ids=True,
                sampling_params={'max_new_tokens': 1, 'temperature': 0},
                return_logprob=True, token_ids_logprob=candidate_ids)
            value = await manager.generate_request(obj, request).__anext__()
            meta = value['meta_info']
            ids = value.get('prompt_token_ids')
            if not isinstance(ids, list) or len(ids) != meta['prompt_tokens']:
                raise RuntimeError('SGLang must return the actual expanded prompt_token_ids matching prompt_tokens')
            image_tokens = ids.count(self.image_token_id)
            if not image_tokens:
                raise RuntimeError('No image tokens reached the model')
            scores_by_id = {token_id: score for score, token_id, _ in meta['output_token_ids_logprobs'][0]}
            scores = [scores_by_id[t] for t in candidate_ids]
            if not all(math.isfinite(v) for v in scores):
                raise RuntimeError('Every candidate must have a finite logprob')
            weights = [math.exp(v-max(scores)) for v in scores]
            probs = [w/sum(weights) for w in weights]
            answers[key] = dict(type='choice', choice=keys[max(range(len(probs)), key=probs.__getitem__)],
                                probabilities=dict(zip(keys, probs)))
            for field, source in [('input_tokens','prompt_tokens'), ('output_tokens','completion_tokens')]:
                usage[field] += meta[source]
            usage['cached_tokens'] += meta.get('cached_tokens', 0)
            readouts[key] = dict(body_sha256=body_hash, body_copies=2,
                text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                prompt_sha256=hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest(),
                input_tokens=len(ids), image_tokens=image_tokens,
                candidate_ids=candidate_ids, candidate_logprobs=scores)
        return dict(model=self.model, answers=answers, usage=usage,
            image_pixels=metadata['image_pixels'],
            image_tokens=sum(row['image_tokens'] for row in readouts.values()),
            inference=dict(metadata, backend='sglang', thinking=False, max_pixels=MAX_PIXELS,
                           candidate_readouts=readouts))
