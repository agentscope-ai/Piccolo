"""Prepare pinned Paddle weights before launching the offline inference server."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request
from .ocr_common import MODELS, verify_models


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--archive-dir',type=Path,help='Reuse verified local archives; do not download')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    all_files={}
    for name,digest in MODELS.items():
        if a.archive_dir:
            candidates=[a.archive_dir/(name+'_infer.tar'),a.archive_dir/(name+'.tar')]
            archive=next((p for p in candidates if p.is_file()),candidates[0])
        else:
            archive=a.out/(name+'_infer.tar')
            if not archive.exists():
                tmp=archive.with_suffix('.download')
                url='https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/'+archive.name
                with urllib.request.urlopen(url,timeout=120) as response, tmp.open('wb') as dst:
                    while chunk:=response.read(1024*1024):dst.write(chunk)
                tmp.replace(archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=digest:
            raise ValueError('OCR archive checksum mismatch: '+name)
        with tarfile.open(archive) as handle:
            members=handle.getmembers()
            for m in members:
                target=(a.out/m.name).resolve()
                if not target.is_relative_to(a.out.resolve()) or not (m.isfile() or m.isdir()):
                    raise ValueError('Unsafe archive member')
                if Path(m.name).parts[0]!=name+'_infer':
                    raise ValueError('Unexpected OCR model directory')
            handle.extractall(a.out,filter='data')
            for m in members:
                if m.isfile():all_files[m.name]=hashlib.sha256((a.out/m.name).read_bytes()).hexdigest()
    receipt={'archive_sha256':MODELS,'files_sha256':all_files}
    tmp=a.out/'verified-models.json.tmp';tmp.write_text(json.dumps(receipt,indent=2)+'\n')
    tmp.replace(a.out/'verified-models.json')
    print(json.dumps({'status':'verified','manifest_sha256':verify_models(a.out)}))


if __name__=='__main__':main()
