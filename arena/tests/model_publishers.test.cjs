const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createHash} = require('node:crypto');
const root = path.resolve(__dirname,'..');
const context = {window:{},document:{baseURI:'https://example.test/prefix/',addEventListener(){}},URL};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root,'web/playground/model-logo.js'),'utf8'),context);
const logos=context.window.JevModelLogo;

test('every current public result has an explicit publisher, local asset and official link', () => {
  for(const name of ['jevbench','decisionindex','harnessjevbench','datajevbench']){
    const document=JSON.parse(fs.readFileSync(path.join(root,'leaderboard',name+'.json'),'utf8'));
    for(const row of document.rows){
      const publisher=logos.resolve(row);
      assert.ok(publisher,row.model_id);
      assert.ok(fs.existsSync(path.join(root,'web',publisher.logo)),publisher.logo);
      assert.ok(publisher.url==='./'||publisher.url.startsWith('https://'),publisher.url);
      const markup=logos.identity(row,row.model_name);
      assert.ok(markup.includes('class="lb-model-link"'),row.model_id);
      assert.ok(markup.includes('rel="noopener noreferrer"'),row.model_id);
      assert.ok(markup.includes(publisher.logo),row.model_id);
    }
  }
});

test('fine-tuned decision models use their publisher rather than the backbone publisher', () => {
  assert.equal(logos.resolve('access-strands-decider-26B-A4B-gemma4-v1-2610').name,'Strands');
  assert.equal(logos.resolve('access-vllm-sr--d3').name,'vLLM Semantic Router');
  assert.equal(logos.resolve('access-Clef-27B-original').name,'Cloudflare');
  assert.equal(logos.resolve('oneshot-w22m05r02-v5best-avg50').name,'AgentScope');
  for(const id of ['oneshot-hosted','oneshot-rl-r6-iter0000019']){
    assert.equal(logos.resolve(id).name,'AgentScope');
    assert.equal(logos.resolve(id).logo,'./playground/logos/agentscope.svg');
    assert.ok(logos.identity({id},'OneShot (27B)').includes('Piccolo (27B)'));
  }
  assert.equal(logos.resolve({model_id:'unknown-fine-tune',model_name:'Qwen Gemma OpenAI'}),null);
  const markup=logos.forModel({model_id:'access-strands-decider-26B-A4B-gemma4-v1-2610',logo:'./playground/logos/qwen.png'});
  assert.ok(markup.includes('strands.webp')&&!markup.includes('qwen.png'));
});

test('AgentScope attribution keeps Piccolo model labels and historical identity unchanged', () => {
  const row=Object.freeze({model_id:'oneshot-w22m05r02-v5best-avg50',model_name:'Piccolo (27B)'});
  const publisher=logos.resolve(row);
  assert.equal(publisher.name,'AgentScope');
  assert.equal(publisher.url,'https://github.com/agentscope-ai/agentscope');
  const markup=logos.identity(row,row.model_name);
  assert.ok(markup.includes('data-model-publisher="AgentScope"'));
  assert.ok(markup.includes('<span>Piccolo (27B)</span>'));
  assert.equal(row.model_name,'Piccolo (27B)');
  assert.equal(row.model_id,'oneshot-w22m05r02-v5best-avg50');
  assert.ok(logos.identity(row,'OneShot 27B RL').includes('<span>Piccolo 27B RL</span>'));
});

test('local logo references resolve correctly behind a path-prefixed deployment', () => {
  const publisher=logos.resolve('access-vllm-sr--d3');
  assert.equal(new URL(publisher.logo,context.document.baseURI).pathname,'/prefix/playground/logos/vllm.webp');
});

test('OpenAI uses the unchanged official black Blossom instead of the blue favicon', () => {
  const publisher=logos.resolve('access-openai--gpt-6-luna-decisions');
  assert.equal(publisher.logo,'./playground/logos/openai.svg');
  const asset=fs.readFileSync(path.join(root,'web',publisher.logo));
  assert.equal(createHash('sha256').update(asset).digest('hex'),
    '7be72f1fea831d3ba81a545cee79b7e0ae69449d5d7837c9571ccbfb4aa1e00b');
  assert.ok(logos.forModel({model_id:'access-openai--gpt-6-luna-decisions',logo:'./playground/logos/openai.png'})
    .includes('src="./playground/logos/openai.svg"'));
});

test('labels are escaped and unsafe image URLs cannot become markup', () => {
  const identity=logos.identity({id:'access-Clef-27B-original'},'<script>alert(1)</script>');
  assert.ok(!identity.includes('<script>'));
  assert.ok(identity.includes('&lt;script&gt;'));
  assert.ok(logos.identity({id:'unknown-custom-model'},'OneShot Research Lab').includes('OneShot Research Lab'));
  for(const value of ['javascript:alert(1)','data:image/svg+xml,test','file:///secret','//elsewhere.test/icon.png','https://u:p@example.test/a.png']){
    assert.equal(logos.markup(value),'',value);
  }
});
