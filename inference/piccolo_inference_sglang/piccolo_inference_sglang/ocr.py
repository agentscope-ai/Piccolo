"""One serialized OCR subprocess. No answer/prompt input and no result cache."""
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from .ocr_common import OCRSettings


class OCRFailure(RuntimeError):
    pass


class OCRWorker:
    def __init__(self, settings):
        self.settings=settings
        self.process=None
        self.identity=None

    async def receive(self,timeout):
        line=await asyncio.wait_for(self.process.stdout.readline(),timeout)
        if not line:raise OCRFailure('OCR process exited; see server stderr')
        try:return json.loads(line)
        except (ValueError,TypeError) as e:raise OCRFailure('Invalid OCR subprocess response') from e

    async def start(self):
        if self.process and self.process.returncode is None:return
        self.process=await asyncio.create_subprocess_exec(self.settings.python,'-u',
            str(Path(__file__).with_name('ocr_worker.py')),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
            limit=16*1024*1024,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        try:
            self.process.stdin.write((json.dumps(asdict(self.settings))+'\n').encode())
            await self.process.stdin.drain()
            response=await self.receive(self.settings.startup_timeout)
            if response.get('ready') is not True:raise OCRFailure('OCR initialization failed; see server stderr: '+response.get('error','unknown'))
            self.identity=response['identity']
        except BaseException:
            await self.close(abort=True);raise

    async def recognize(self,url):
        await self.start()
        token=uuid.uuid4().hex
        try:
            self.process.stdin.write((json.dumps({'id':token,'image_data':url})+'\n').encode())
            await self.process.stdin.drain()
            result=await self.receive(self.settings.timeout)
            if result.get('id')!=token or result.get('ok') is not True:
                raise OCRFailure('OCR image processing failed; no fallback to empty text')
            if not isinstance(result.get('text'),str):raise OCRFailure('OCR returned invalid text')
            return result
        except BaseException:
            # Never allow a timed-out response to be consumed by the next request.
            await self.close(abort=True);raise

    async def close(self, *, abort=False):
        process=self.process;self.process=None
        if process is not None:
            if not abort and process.returncode is None:
                # EOF lets Paddle exit normally without a native SIGTERM traceback.
                process.stdin.close()
                try:
                    await asyncio.wait_for(process.wait(),5)
                    return
                except asyncio.TimeoutError:pass
            if process.returncode is None:
                try:process.terminate()
                except ProcessLookupError:pass
            try:await asyncio.wait_for(process.wait(),5)
            except asyncio.TimeoutError:
                process.kill();await process.wait()


class OCRPool:
    def __init__(self,settings=None):
        self.settings=settings or OCRSettings.from_env()
        self.workers=[OCRWorker(self.settings)] if self.settings.enabled else []
        self.queue=asyncio.Queue()
        self.start_lock=asyncio.Lock()
        self.started=False

    async def start(self):
        if not self.settings.enabled:return
        async with self.start_lock:
            if self.started:return
            results=await asyncio.gather(*(w.start() for w in self.workers),return_exceptions=True)
            if any(isinstance(r,BaseException) for r in results):
                await asyncio.gather(*(w.close() for w in self.workers))
                raise OCRFailure('Unable to initialize frozen OCR workers; inspect server stderr')
            for w in self.workers:self.queue.put_nowait(w)
            self.started=True

    async def recognize(self,urls):
        await self.start()
        if not self.settings.enabled:return None,{'enabled':False}
        started=time.perf_counter()
        async def one(url):
            worker=await self.queue.get()
            try:return await worker.recognize(url)
            finally:self.queue.put_nowait(worker)
        tasks=[asyncio.create_task(one(url)) for url in urls]
        try:results=await asyncio.gather(*tasks)
        except BaseException:
            for t in tasks:t.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            raise
        # gather preserves input order even when images finish out of order.
        texts=[r['text'] for r in results]
        return texts,dict(self.runtime(),image_sha256=[r['image_sha256'] for r in results],
            text_sha256=[hashlib.sha256(t.encode()).hexdigest() for t in texts],
            text_characters=[len(t) for t in texts],line_counts=[r['line_count'] for r in results],
            image_service_ms=[r['milliseconds'] for r in results],
            branch_wall_ms_including_worker_wait=(time.perf_counter()-started)*1000)

    def runtime(self):
        return dict(self.settings.public(),ready=self.started,
                    worker_identity=[w.identity for w in self.workers if w.identity])

    async def close(self):
        await asyncio.gather(*(w.close() for w in self.workers))
        self.started=False
        self.queue=asyncio.Queue()
