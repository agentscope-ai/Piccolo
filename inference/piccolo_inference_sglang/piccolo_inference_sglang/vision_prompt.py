"""Pure prompt/image contract; imports no SGLang or Paddle runtime."""
import base64
import hashlib
import io
import json
from PIL import Image

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


def prepare_images(images, max_images=4):
    if not isinstance(images, list) or not 1 <= len(images) <= max_images:
        raise ValueError(f'the canvas holds 1..{max_images} images per request')
    urls, pixels, hashes = [], [], []
    for ref in images:
        url, count = image_url(ref)
        urls.append(url)
        pixels.append(count)
        hashes.append(hashlib.sha256(base64.b64decode(url.split(',', 1)[1])).hexdigest())
    return urls, pixels, hashes


def conversations(state, questions, images, prompt, max_images=4, *, prepared_images=None):
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
    urls, pixels, hashes = prepared_images if prepared_images is not None else prepare_images(images,max_images)
    if not len(urls)==len(pixels)==len(hashes)==len(images):
        raise ValueError('Prepared images do not align with original images')
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

