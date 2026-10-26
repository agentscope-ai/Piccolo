/* Independent text play: a single 16-way choice, with honest probability coverage. */
(()=>{
 'use strict';
 const kind='mbti_text',types=['ESTJ','ESTP','ESFJ','ESFP','ENTJ','ENTP','ENFJ','ENFP','ISTJ','ISTP','ISFJ','ISFP','INTJ','INTP','INFJ','INFP'];
 const traits={E:'Extraversion',I:'Introversion',S:'Sensing',N:'Intuition',T:'Thinking',F:'Feeling',J:'Judging',P:'Perceiving'};
 const maxChars=8000;let serial=0,pending=false,lastModel=null,latestResult=null;
 const stylesheet=document.createElement('link');stylesheet.rel='stylesheet';stylesheet.href='./playground/mbti.css?v=header-clean-20261015-v1';document.head.append(stylesheet);
 const panel=document.createElement('section');panel.id='mbtiPlay';panel.className='mbti-play hidden';panel.setAttribute('aria-labelledby','mbtiTitle');
 panel.innerHTML=JevPlayText.html(`<header class="mbti-header"><div><div class="scene-kicker">TEXT LAB · 16 TYPES</div><h2 id="mbtiTitle">MBTI Text Test</h2><p>Explore the tendencies expressed in a piece of text.</p></div></header>
 <div class="mbti-layout"><div class="mbti-editor"><label for="mbtiText">Your text</label><textarea id="mbtiText" rows="8" placeholder="Add a description, journal entry, conversation or thought."></textarea><div class="mbti-editor-foot"><span id="mbtiCount">0 / 8,000 characters</span><button id="mbtiExample" type="button">Try an example</button></div><p class="mbti-help">Results describe this text, not the author’s fixed personality.</p><button id="mbtiRun" class="primary" type="button">Analyze text ↗</button><div id="mbtiStatus" role="status" aria-live="polite"></div></div>
 <aside class="mbti-answer"><span class="scene-kicker">TEXT TENDENCY</span><div id="mbtiType" class="mbti-type">????</div><div id="mbtiTraits">Start with a few words</div><div id="mbtiModel" class="mbti-model"></div><div id="mbtiTiming"></div></aside></div>
 <div class="mbti-prob-header"><h3 id="mbtiProbabilityTitle">16 candidate types</h3><span id="mbtiCoverage"></span></div><div id="mbtiCandidates" class="mbti-candidates"></div>
 <details id="mbtiEvidence"><summary>Source and model input</summary><p id="mbtiProbabilityNote" class="mbti-help"></p><h4>Source</h4><pre id="mbtiSource" class="content"></pre><h4>Original TrainingRecord</h4><pre id="mbtiRecord" class="content"></pre><h4 id="mbtiInputTitle">Model input</h4><pre id="mbtiInput" class="content"></pre></details>`);
 $('showcasesView').insertAdjacentElement('afterend',panel);
 function candidates(result=null){
  latestResult=result;
  const rows=new Map((result?.distribution||[]).map(x=>[x.value,x]));
  const complete=result?.probability_coverage?.complete!==false&&types.every(t=>Number.isFinite(rows.get(t)?.probability));
  const partial=!!result&&!complete;
  $('mbtiProbabilityTitle').textContent=JevPlayText.ui(partial?'16 types · Observed token probabilities':result?'16 types · Normalized probabilities':'16 candidate types');
  $('mbtiCoverage').textContent=JevPlayText.ui(result?(partial?'Partial response · Missing values stay missing':'Complete · 16 / 16'):'');
  const cells=types.map(type=>{
   const row=rows.get(type),p=partial?row?.raw_token_probability:row?.probability;
   const valid=Number.isFinite(p)&&p>=0&&p<=1;
   const cell=document.createElement('div');cell.className='mbti-candidate'+(result?.value===type?' selected':'');cell.dataset.type=type;
   const heading=document.createElement('div');heading.className='mbti-candidate-heading';
   const name=document.createElement('strong');name.textContent=JevPlayText.ui(type);
   const score=document.createElement('b');score.className='mbti-value';score.textContent=JevPlayText.ui(valid?(100*p).toFixed(2)+'%':result?'Unavailable':'—');
   heading.append(name,score);cell.append(heading);
   const track=document.createElement('div');track.className='mbti-track'+(!valid?' missing':'');
   if(valid){const fill=document.createElement('span');fill.style.width=(100*p)+'%';track.append(fill)}
   cell.append(track);return cell;
  });$('mbtiCandidates').replaceChildren(...cells);
  $('mbtiProbabilityNote').textContent=JevPlayText.ui(result?(partial?'Missing probabilities are unavailable; observed values are not normalized.':'Probabilities describe relative preference, not calibrated accuracy.'):'');
 }
 function reset(){serial++;$('mbtiType').textContent=JevPlayText.ui('????');$('mbtiTraits').textContent=JevPlayText.ui('Ready to analyze');$('mbtiModel').textContent=JevPlayText.ui('');$('mbtiTiming').textContent=JevPlayText.ui('');$('mbtiStatus').textContent=JevPlayText.ui('');$('mbtiSource').textContent='';$('mbtiRecord').textContent='';$('mbtiInput').textContent='';$('mbtiEvidence').open=false;candidates()}
 function count(){const n=Array.from($('mbtiText').value).length;$('mbtiCount').textContent=JevPlayText.ui(n.toLocaleString(window.JevI18n?.lang==='zh'?'zh-CN':'en-US')+' / 8,000 characters');$('mbtiCount').classList.toggle('mbti-error',n>maxChars);return n}
 function controls(){const invalid=!$('mbtiText').value.trim()||count()>maxChars;$('mbtiRun').disabled=pending||invalid;$('mbtiText').disabled=pending;$('mbtiExample').disabled=pending;$('mbtiRun').textContent=JevPlayText.ui(pending?'Reading…':'Analyze text ↗');panel.setAttribute('aria-busy',String(pending))}
 function activate(selected,visible){const active=selected===kind;panel.classList.toggle('hidden',!active||!visible);if(!active&&pending)serial++;return active}
 function open(value){if(value!==kind)return false;if(showcaseBusy||busy)return true;stopAuto();window.JevRacingUI?.deactivate();selectedPlay=kind;showcaseKind=null;showcaseSession=null;activatePlay(true);markPicker();JevSeedUI.show(null,false,false);if(lastModel!==modelName){reset();lastModel=modelName}controls();$('mbtiText').focus();return true}
 async function classify(){
  if(pending)return;
  if(!$('mbtiText').value.trim()){$('mbtiStatus').textContent=JevPlayText.ui('Add some text first.');return}
  if(count()>maxChars){$('mbtiStatus').textContent=JevPlayText.ui('Please shorten the text to 8,000 characters. It will not be truncated.');return}
  reset();const request=serial,requestedModel=modelName,input=$('mbtiText').value;pending=true;controls();$('mbtiStatus').textContent=JevPlayText.ui('Reading your text…');
  try{
   const response=await api('mbti/classify',{text:input});
   if(request!==serial||selectedPlay!==kind||modelName!==requestedModel)return;
   const result=response.result;lastModel=requestedModel;
   $('mbtiType').textContent=JevPlayText.ui(result.value);$('mbtiTraits').textContent=JevPlayText.ui([...result.value].map(x=>traits[x]).join(' · '));
   $('mbtiModel').textContent=JevPlayText.ui('Model: ')+(modelChoices[result.model]||result.model_label||result.model);
   $('mbtiTiming').textContent=JevPlayText.ui(Number.isFinite(result.latency_seconds)?'Time: '+result.latency_seconds.toFixed(2)+' s':'');
   $('mbtiStatus').textContent=JevPlayText.ui('Analysis complete');candidates(result);
   $('mbtiSource').textContent=pretty({source:result.source,model:result.model,served_model:result.served_model,template_version:result.template_version});
   $('mbtiRecord').textContent=pretty(response.record);
   $('mbtiInputTitle').textContent=JevPlayText.ui(result.model_input?.format==='typesafe-systemone-schema'?'Sent API schema':'Model input · messages / assistant suffix');
   $('mbtiInput').textContent=result.model_input?pretty(result.model_input):'This API does not return its internal prompt. See the original record above.';
  }catch(e){if(request===serial&&selectedPlay===kind&&modelName===requestedModel)$('mbtiStatus').textContent=JevPlayText.ui(e.message||'Model request failed. Please retry.')}
  finally{pending=false;controls();if(request!==serial&&selectedPlay===kind)$('mbtiStatus').textContent=JevPlayText.ui('The selection changed; the previous response was skipped.')}
 }
 $('mbtiText').addEventListener('input',()=>{reset();controls()});$('mbtiRun').addEventListener('click',classify);
 $('mbtiExample').addEventListener('click',()=>{$('mbtiText').value=window.JevI18n?.t('This weekend I want to organize my notes alone and connect a few seemingly unrelated ideas. When opinions differ, I compare the reasoning behind each option and leave room to adjust as new information arrives.','周末我想先独自整理笔记，把几个看似无关的想法连起来。遇到分歧时，我会比较各方案的逻辑，再留一些空间根据新信息调整。')??'This weekend I want to organize my notes alone and connect a few seemingly unrelated ideas. When opinions differ, I compare the reasoning behind each option and leave room to adjust as new information arrives.';reset();controls()});
 $('modelSelect').addEventListener('change',()=>{if(selectedPlay===kind){reset();lastModel=null;controls()}});
 window.JevTextPlays={items:[{id:kind,name:'MBTI Text Test'}],open,activate};
 playIcons[kind]='✦';playTaglines[kind]='16-type classification';compactNames[kind]='MBTI Text Test';
 function refreshLanguage(){
  const copy={'.mbti-header .scene-kicker':'TEXT LAB · 16 TYPES','#mbtiTitle':'MBTI Text Test','.mbti-header p':'Explore the tendencies expressed in a piece of text.','label[for="mbtiText"]':'Your text','#mbtiExample':'Try an example','.mbti-editor > .mbti-help':'Results describe this text, not the author’s fixed personality.','.mbti-answer > .scene-kicker':'TEXT TENDENCY','#mbtiEvidence > summary':'Source and model input','#mbtiEvidence > h4:nth-of-type(1)':'Source','#mbtiEvidence > h4:nth-of-type(2)':'Original TrainingRecord'};
  for(const [selector,en] of Object.entries(copy)){const element=panel.querySelector(selector);if(element)element.textContent=JevPlayText.ui(en);}
  $('mbtiText').placeholder=JevPlayText.ui('Add a description, journal entry, conversation or thought.');
  for(const id of ['mbtiStatus','mbtiTiming','mbtiInputTitle'])$(id).textContent=JevPlayText.ui($(id).textContent);
  $('mbtiModel').textContent=latestResult?JevPlayText.ui('Model: ')+(modelChoices[latestResult.model]||latestResult.model_label||latestResult.model):'';
  $('mbtiTraits').textContent=JevPlayText.ui(latestResult?[...latestResult.value].map(x=>traits[x]).join(' · '):'Ready to analyze');
  candidates(latestResult);controls();
 }
 window.JevI18n?.onChange(refreshLanguage);
 candidates();controls();renderPlayPicker();
})();
