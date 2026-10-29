"""Check the deployed backend without reading or printing its provider token."""
import argparse
import json
import time
import uuid

import httpx


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8080/')
    args=parser.parse_args()
    with httpx.Client(base_url=args.url.rstrip('/')+'/',timeout=90,follow_redirects=False) as client:
        response=client.get('api/v1/models')
        response.raise_for_status()
        model=next(m for m in response.json()['models'] if m['id']=='oneshot-hosted')
        if not model['ready']:
            print(json.dumps({'ok':False,'code':'hosted_model_not_configured'}));return 1
        start=time.perf_counter()
        result=client.post('api/v1/decisions',json={'model_id':model['id'],'input':{
            'request_id':uuid.uuid4().hex,'model':model['served_model'],'game':'blackjack',
            'observation':{'hand':[8,2],'dealer_upcard':'Q','goal':'不超过21点并胜过庄家'},
            'question':{'id':'decision','instructions':'选择下一步动作。',
                'options':[{'id':'hit','label':'要牌'},{'id':'stand','label':'停牌'}]}}})
        data=result.json() if result.status_code==200 else {}
        ok=result.status_code==200 and data.get('action') in ('hit','stand')
        print(json.dumps({'ok':ok,'status':result.status_code,'model':model['served_model'],
            'action':data.get('action') if ok else None,'seconds':round(time.perf_counter()-start,3)}))
        return 0 if ok else 1


if __name__=='__main__':
    raise SystemExit(main())
