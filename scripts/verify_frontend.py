"""Check the local Piccolo application; never call a model or publish a site."""
import argparse,json,os,socket,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--server-python', default=sys.executable)
args=parser.parse_args()
server_python=os.path.abspath(args.server_python)
art=root/'var/verification';art.mkdir(parents=True,exist_ok=True)
with socket.socket() as sock:
 sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
base=f'http://127.0.0.1:{port}'
with tempfile.TemporaryDirectory(prefix='blink-app-check-') as tmp:
 env=os.environ.copy();env.update(JEV_DATA_DIR=tmp,JEV_CONFIG=str(root/'arena/config/app.json'),JEV_LEADERBOARD_DIR=str(root/'arena/leaderboard'),PYTHONPATH=str(root/'arena'))
 log=open(art/'server.log','w')
 proc=subprocess.Popen([server_python,'-m','blink_arena','--host','127.0.0.1','--port',str(port)],cwd=root/'arena',env=env,stdout=log,stderr=log)
 report={'views':[],'errors':[]}
 try:
  for _ in range(120):
   try:
    with urllib.request.urlopen(base+'/api/health',timeout=1) as r:assert r.status==200
    break
   except Exception:time.sleep(.2)
  else:raise RuntimeError('Local app did not become healthy')
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True,args=['--no-sandbox'],channel=os.environ.get('BLINK_BROWSER_CHANNEL'))
   for device,width,height in [('desktop',1440,1000),('mobile',390,844)]:
    page=browser.new_page(viewport={'width':width,'height':height})
    page.on('pageerror',lambda error:report['errors'].append(str(error)))
    page.goto(base,wait_until='networkidle')
    for lang in ['en','zh']:
     page.locator(f'[data-language="{lang}"]').click()
     assert page.locator('.brand strong').inner_text().strip()=='Piccolo'
     assert 'Piccolo' in page.title()
     for tab in ['blog','leaderboard','games']:
      page.locator(f'.tabs [data-tab="{tab}"]').click()
      page.wait_for_timeout(350)
      assert not page.locator('.mast').evaluate("n=>/OneShot|GameJevArena/.test(n.innerText)")
      assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+1')
     page.locator('.tabs [data-tab="leaderboard"]').click()
     for benchmark in ['jevbench','decisionindex','harnessjevbench','datajevbench','gamejevbench']:
      page.locator(f'#leaderboardTabs [data-benchmark="{benchmark}"]').click()
      page.wait_for_timeout(200)
      assert not page.locator('body').evaluate(r"n=>/\bBlink\b|\bBLINK\b/.test(n.innerText)")
      assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth+1')
     report['views'].append({'device':device,'language':lang,'tabs':3,'benchmarks':5})
     page.screenshot(path=str(art/f'piccolo-{device}-{lang}.png'))
    page.close()
   browser.close()
  assert not report['errors'],report['errors']
  (art/'browser.json').write_text(json.dumps(report,indent=2))
  print(json.dumps(report))
 finally:
  proc.terminate()
  try:proc.wait(timeout=10)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
  log.close()
