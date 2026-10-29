(function () {
  'use strict';
  const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  // Publisher attribution is bound to exact result IDs, never inferred from a base-model name.
  // Official pages and local asset provenance: logos/PUBLISHER_SOURCES.md.
  const publishers={
    oneshot:{name:'AgentScope',logo:'./playground/logos/agentscope.svg',url:'https://github.com/agentscope-ai/agentscope'},
    startlux:{name:'StartLux',logo:'./playground/logos/startlux.webp',url:'https://huggingface.co/startlux-models/StartLux-Decision-v1.1-27B-Instant'},
    strands:{name:'Strands',logo:'./playground/logos/strands.webp',url:'https://huggingface.co/StrandsAgents/strands-decider-26B-A4B-gemma4-v1-2610'},
    cloudflare:{name:'Cloudflare',logo:'./playground/logos/cloudflare.png',url:'https://blog.cloudflare.com/clef-decision-models/'},
    microsoft:{name:'Microsoft',logo:'./playground/logos/microsoft.ico',url:'https://commandline.microsoft.com/microsoft-decision-1-model-foundry/'},
    inception:{name:'Inception',logo:'./playground/logos/inception.png',url:'https://www.inceptionlabs.ai/blog/introducing-mercury-3'},
    openai:{name:'OpenAI',logo:'./playground/logos/openai.svg',url:'https://developers.openai.com/api/docs/guides/decisions'},
    typesafe:{name:'TypeSafe',logo:'./playground/logos/typesafe.png',url:'https://typesafe.ai/blog/jev-1-14'},
    vllm:{name:'vLLM Semantic Router',logo:'./playground/logos/vllm.webp',url:'https://huggingface.co/vllm-sr/d3/tree/v3.1.0'},
    perplexity:{name:'Perplexity',logo:'./playground/logos/perplexity.svg',url:'https://huggingface.co/perplexity-ai/pplx-decider-v1.2'},
    qwen:{name:'Qwen',logo:'./playground/logos/qwen.png',url:'https://qwen.ai/'}
  };
  const modelPublishers={
    'blink-27b-1028':'oneshot',
    'blink-9b-1028':'oneshot',
    'blink-4b-1028':'oneshot',
    'oneshot-hosted':'oneshot',
    'oneshot-rl-r6-iter0000019':'oneshot',
    'ours-w22m05r02-v5best-avg50':'oneshot',
    'oneshot27b-100k-iter999':'oneshot',
    'oneshot27b-100k-iter1971':'oneshot',
    'oneshot-w22m05r02-v5best-avg50':'oneshot',
    'oneshot27b-control-reviewed-sft-iter310':'oneshot',
    'oneshot27b-gameplay-terminal-rl4':'oneshot',
    'oneshot27b-game-rl-native-iter17':'oneshot',
    'access-StartLux-Decision-v1.1-27B-Instant':'startlux',
    'access-strands-decider-26B-A4B-gemma4-v1-2610':'strands',
    'access-Clef-27B-original':'cloudflare',
    'access-microsoft--microsoft-decision-1':'microsoft',
    'access-inception--mercury-decide':'inception',
    'access-openai--gpt-6-luna-decisions':'openai',
    'access-typesafe--jev-1.14':'typesafe',
    'access-vllm-sr--d3':'vllm',
    'access-perplexity-ai--pplx-decider-v1.2':'perplexity',
    'access-qwen38-27b':'qwen',
    'access-qwen3.8-27b-chat-Direct-v1':'qwen',
    'qwen3.8-27b-base':'qwen',
    'qwen3.6-35b-a3b-base':'qwen',
    'qwen3.8-27b-dashscope':'qwen',
    'qwen3.8-max-dashscope':'qwen',
    'qwen3.6-35b-a3b-dashscope':'qwen',
    'dashscope-qwen3.8-max':'qwen',
    'dashscope-qwen3.6-35b-a3b':'qwen'
  };
  function resolve(row) {
    const id=typeof row==='string'?row:row?.model_key||row?.model_id||row?.id||row?.source_id;
    return publishers[modelPublishers[id]]||null;
  }
  function markup(value,publisher='') {
    if(typeof value!=='string'||!value||/[\s\\\u0000-\u001f]/.test(value)||value.startsWith('//'))return '';
    try {
      const url=new URL(value,document.baseURI);
      if(!['http:','https:'].includes(url.protocol)||url.username||url.password)return '';
    } catch {return '';}
    return '<img class="lb-model-logo" src="'+escape(value)+'" width="20" height="20" alt=""'+(publisher?' title="'+escape(publisher)+'"':'')+' decoding="async" referrerpolicy="no-referrer">';
  }
  function forModel(row) {
    const publisher=resolve(row);
    return markup(publisher?.logo||row?.logo,publisher?.name||'');
  }
  function identity(row,label) {
    const publisher=resolve(row);
    const display=publisher===publishers.oneshot?String(label).replace(/^(?:OneShot|QwenJev|Blink)\b/i,'Piccolo'):label;
    const content=forModel(row)+'<span>'+escape(display)+'</span>';
    if(!publisher)return content;
    const hint=window.JevI18n?.t('Official page · opens in a new tab','官方页面 · 在新标签页打开')||'Official page · opens in a new tab';
    return '<a class="lb-model-link" href="'+escape(publisher.url)+'" target="_blank" rel="noopener noreferrer" data-model-publisher="'+escape(publisher.name)+'" title="'+escape(publisher.name+' · '+hint)+'">'+content+'</a>';
  }
  // A missing optional asset leaves the name intact, without a broken-image box.
  document.addEventListener('error',event=>{
    if(event.target instanceof HTMLImageElement&&event.target.classList.contains('lb-model-logo'))event.target.hidden=true;
  },true);
  window.JevModelLogo={markup,forModel,identity,resolve};
})();
