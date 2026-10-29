"""Run frontend and API together with one process; no model configuration required."""
import argparse
import os
import uvicorn
from .app import create_app

def main():
    parser = argparse.ArgumentParser(description='PiccoloArena frontend and engine API')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--prefix', default=os.environ.get('JEV_PREFIX',''))
    args = parser.parse_args()
    app = create_app(prefix=args.prefix, frontend=f'http://127.0.0.1:{args.port}'+args.prefix.rstrip('/'))
    uvicorn.run(app,host=args.host,port=args.port,access_log=False)

if __name__ == '__main__': main()
