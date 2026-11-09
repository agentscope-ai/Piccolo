"""Request question list -> complete body -> ordered images -> identical body.

Image resizing follows decision_index.vision (see licenses/Decision-Index-MIT.txt).
"""
import asyncio
import base64
import hashlib
import io
import json
import math
import time

from fastapi import Request
from starlette.responses import JSONResponse
from PIL import Image
from transformers import AutoTokenizer

from .vision_prompt import MAX_PIXELS, LETTERS, conversations, prepare_images
from .ocr import OCRPool
from .ocr_common import inject_ocr


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
        self.ocr = OCRPool()

    async def close(self):
        await self.ocr.close()

    async def runtime(self):
        await self.ocr.start()
        return dict(backend='sglang',ocr=self.ocr.runtime(),
                    vision_format='question_list_text_images_text',
                    prompt_revision=('20261030+ocr-state-once-20261102'
                                     if self.ocr.settings.enabled else '20261030'),
                    ocr_dependency=('OCR completes before the decision forward pass'
                                    if self.ocr.settings.enabled else 'disabled'))

    async def runtime_handle(self):
        try:
            return JSONResponse(await self.runtime())
        except (RuntimeError,OSError,asyncio.TimeoutError):
            return JSONResponse({'error':'OCR initialization failed; see server stderr'},status_code=503)

    async def handle(self, request: Request):
        try:
            body = await request.json()
            if not isinstance(body,dict):raise ValueError('request must be an object')
            return JSONResponse(await self.infer(body, request))
        except (ValueError, KeyError, TypeError) as error:
            return JSONResponse({'error': str(error)}, status_code=422)
        except (RuntimeError, OSError, asyncio.TimeoutError):
            # No silent no-OCR prediction when the frozen branch fails.
            return JSONResponse({'error': 'Inference failed; inspect server stderr'}, status_code=502)

    async def infer(self, body, request):
        from sglang.srt.entrypoints.http_server import get_global_state
        manager = get_global_state().tokenizer_manager

        started=time.perf_counter()
        if body.get('model', self.model) != self.model:
            raise ValueError('model must match the served model')
        prepared=await asyncio.to_thread(prepare_images,body['images'])
        prompt_task=asyncio.create_task(asyncio.to_thread(conversations,
            body['state'],body['questions'],body['images'],body.get('prompt'),prepared_images=prepared))
        ocr_task=asyncio.create_task(self.ocr.recognize(prepared[0]))
        try:
            (rows, images, metadata),(texts,ocr_metadata)=await asyncio.gather(prompt_task,ocr_task)
        except BaseException:
            prompt_task.cancel();ocr_task.cancel()
            await asyncio.gather(prompt_task,ocr_task,return_exceptions=True)
            raise
        if texts is not None:
            if ocr_metadata['image_sha256'] != metadata['image_sha256']:
                raise RuntimeError('OCR and decision model saw different image bytes/order')
            rows=inject_ocr(rows,body['state'],texts,len(images))
            metadata['prompt_revision']='20261030+ocr-state-once-20261102'
        metadata['ocr']=ocr_metadata
        ready=time.perf_counter()
        # While this request uses the GPU reader, following requests can do OCR.
        # A request's own reader still depends on its completed OCR text.
        async with self.lock:
            acquired=time.perf_counter()
            result=await self.run_rows(rows,images,metadata,manager,request)
        finished=time.perf_counter()
        result['inference']['timing_ms']=dict(
            server_total_including_wait=(finished-started)*1000,
            preparation_including_ocr=(ready-started)*1000,
            reader_lock_wait=(acquired-ready)*1000,
            reader_stage_wall=(finished-acquired)*1000,
            note='Reader time includes tokenizer/backend scheduling; not isolated GPU kernel latency.')
        return result

    async def run_rows(self, rows, images, metadata, manager, request):
        from sglang.srt.managers.io_struct import GenerateReqInput
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
