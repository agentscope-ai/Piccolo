"""Persistent JSON-lines pixel-only worker, run in a separate Paddle environment."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time


def main():
    # Native Paddle logs also go to stderr; keep protocol stdout uncontaminated.
    protocol=os.fdopen(os.dup(1),'w',buffering=1)
    os.dup2(2,1)
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from piccolo_inference_sglang.ocr_common import verify_models, MODELS
    config=json.loads(sys.stdin.readline())
    try:
        identity=verify_models(config['model_dir'])
        os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True'
        import paddle
        from paddleocr import PaddleOCR
        from importlib.metadata import version
        import numpy as np
        from PIL import Image
        device=config['device']
        if device.startswith('gpu:') and not paddle.device.is_compiled_with_cuda():
            raise RuntimeError('GPU OCR requested but this Paddle build has no CUDA')
        if device.startswith('gpu:'):paddle.set_device(device)
        root=Path(config['model_dir']);det,rec=list(MODELS)
        pipeline=PaddleOCR(text_detection_model_name=det,text_detection_model_dir=str(root/(det+'_infer')),
            text_recognition_model_name=rec,text_recognition_model_dir=str(root/(rec+'_infer')),
            use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,
            device=device,enable_mkldnn=False,cpu_threads=config['cpu_threads'],
            text_det_limit_side_len=960,text_det_limit_type='max',text_recognition_batch_size=8)
        protocol.write(json.dumps({'ready':True,'identity':{'manifest_sha256':identity,'device':device,
            'packages':{n:version(n) for n in ['paddleocr','paddlex','numpy','Pillow']},'paddle':paddle.__version__}})+'\n')
    except Exception as e:
        print('OCR initialization failed: '+type(e).__name__+': '+str(e),file=sys.stderr,flush=True)
        protocol.write(json.dumps({'ready':False,'error':type(e).__name__+': '+str(e)})+'\n')
        return 1
    for line in sys.stdin:
        req={}
        try:
            req=json.loads(line)
            if set(req)!={'id','image_data'}:raise ValueError('Worker accepts image pixels only')
            raw=base64.b64decode(req['image_data'].split(',',1)[1],validate=True)
            start=time.perf_counter()
            with Image.open(io.BytesIO(raw)) as im:
                if im.width*im.height>1638400:raise ValueError('Image must be capped before OCR')
                bgr=np.asarray(im.convert('RGB'))[:,:,::-1].copy()
            if device!='cpu':paddle.device.synchronize(device)
            results=list(pipeline.predict(bgr))
            if device!='cpu':paddle.device.synchronize(device)
            if len(results)!=1:raise ValueError('Expected one result for one image')
            value=results[0].json
            if isinstance(value,str):value=json.loads(value)
            value=value.get('res',value)
            lines=value['rec_texts']
            if any(not isinstance(t,str) for t in lines):raise ValueError('Invalid OCR text')
            scores=[float(x) for x in value['rec_scores']]
            if len(lines)!=len(scores):raise ValueError('OCR text/score count mismatch')
            response={'id':req['id'],'ok':True,'text':'\n'.join(lines),'line_count':len(lines),
                      'image_sha256':hashlib.sha256(raw).hexdigest(),
                      'milliseconds':(time.perf_counter()-start)*1000}
        except Exception as e:
            print('OCR processing failed: '+type(e).__name__+': '+str(e),file=sys.stderr,flush=True)
            response={'id':req.get('id'),'ok':False,'error':type(e).__name__+': '+str(e)}
        protocol.write(json.dumps(response,ensure_ascii=False,allow_nan=False)+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
