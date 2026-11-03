// Representative 27B experiments from the team's original evolution figure.
// The controlled reading retest and complementary-branch comparison are separate.
const milestones = [
  {score:48.91, phase:0, title:['27B base model','27B 基座模型'], text:['Measure the starting point on the full-suite Decision Index.','在全集 Decision Index 上测量共同起点。']},
  {score:56.68, phase:0, title:['Prepare the decision data','整理决策数据'], text:['Normalize source material and establish supervision over the candidate set.','统一来源材料，建立面向候选集合的监督。']},
  {score:59.09, phase:0, title:['Refine the data mixture','细化数据配比'], text:['Use task labels to balance background and targeted material, then continue from a stronger checkpoint.','依据任务标签调整背景与定向材料，从较好的模型继续训练。']},
  {score:60.92, phase:1, title:['Change how the question is read','调整题面信息交互'], text:['Explore bidirectional attention so the question and its candidates can refer to one another.','探索双向注意力，让问题与候选信息相互参考。']},
  {score:62.39, phase:1, title:['Stage the training','分阶段安排训练'], text:['Give broad coverage and targeted strengthening different roles in the training recipe.','分别安排广泛覆盖与定向加强，使数据在不同阶段承担不同作用。']},
  {score:63.84, phase:1, title:['Combine complementary work','组合互补探索'], text:['Bring retrieval, task additions, background replay and complementary models into the next recipe.','将语义检索、任务补充、背景回放与互补模型带入后续配方。']},
  {score:65.47, phase:1, title:['Add judgment and preference tasks','补齐判断与偏好任务'], text:['Target specific decision relations, including tool applicability, information sufficiency and candidate preference.','围绕工具适用性、信息充分性与候选偏好，补充具体的判断关系。']},
  {score:66.65, phase:2, title:['Adapt the reading format','适配读题方式'], text:['Explore question placement and repeated reading alongside the attention and input settings.','结合注意力与输入设置，探索问题前置和重复阅读。']},
  {score:67.44, phase:2, title:['Align training and input','对齐训练与输入'], text:['Match the training input, attention behavior and targeted supervision to the decision interface.','使训练输入、注意力行为与定向监督匹配实际决策接口。']},
  {score:68.33, phase:2, title:['Supplement targeted tasks','定向补充任务'], text:['Carry the useful recipe forward and add examples around the remaining capability gaps.','继承有效配方，围绕仍未掌握的能力补充样本。']},
  {score:68.59, phase:2, title:['Continue with scoring and pragmatics','评分与语用数据续训'], text:['Use sample-level feedback to guide data selection and further scoring and pragmatic-language supervision.','依据逐题反馈选择数据，继续补充评分与语用判断监督。']}
];
const phases = [
  {name:['Data recipes','数据与配比'],start:0,end:2},
  {name:['Training and coverage','训练与能力'],start:3,end:6},
  {name:['Reading and feedback','读题与反馈'],start:7,end:10}
];
export {milestones as evolutionMilestones};
const ns='http://www.w3.org/2000/svg';
const node=(tag,cls='',text)=>{
  const result=document.createElement(tag);
  if(cls)result.className=cls;
  if(text!==undefined)result.textContent=text;
  return result;
};
const shape=(tag,attrs={},text)=>{
  const result=document.createElementNS(ns,tag);
  Object.entries(attrs).forEach(([name,value])=>result.setAttribute(name,String(value)));
  if(text!==undefined)result.textContent=text;
  return result;
};
const control=(text,callback,key)=>{
  const result=node('button','',text);
  result.type='button';
  result.dataset.evControl=key;
  result.addEventListener('click',callback);
  return result;
};

export function mountEvolution(host) {
  const locale=window.JevI18n;
  const t=(en,zh)=>locale.t(en,zh);
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let index=milestones.length-1,playing=false,visible=false,timer=0,destroyed=false;
  const stop=()=>{playing=false;clearTimeout(timer);timer=0;};
  function schedule() {
    clearTimeout(timer);timer=0;
    if(!playing||!visible||document.hidden||destroyed)return;
    timer=setTimeout(()=>{
      if(index===milestones.length-1)stop();
      else {index++;if(index===milestones.length-1)stop();}
      render();
      schedule();
    },2100);
  }
  function select(next,key) {
    stop();index=Math.max(0,Math.min(milestones.length-1,next));
    render(key);
  }
  function chart() {
    const svg=shape('svg',{viewBox:'0 0 960 370',role:'img','aria-label':t('27B full-suite Decision Index: ','27B 全集 Decision Index：')+milestones.map(point=>point.score.toFixed(2)).join(' → ')});
    const x=i=>70+i*82;
    const y=score=>322-(score-45)/25*185;
    const phaseBounds=[[50,275],[275,603],[603,915]];
    phases.forEach((phase,i)=>{
      const [left,right]=phaseBounds[i];
      svg.append(shape('rect',{x:left,y:8,width:right-left,height:332,class:'ev27-phase-band phase-'+i}));
      svg.append(shape('text',{x:(left+right)/2,y:37,'text-anchor':'middle',class:'ev27-lane-label'},t(...phase.name)));
    });
    for(const value of [50,60,70]) {
      svg.append(shape('line',{x1:50,y1:y(value),x2:915,y2:y(value),class:'ev27-gridline'}));
      svg.append(shape('text',{x:35,y:y(value)+4,'text-anchor':'end',class:'ev27-y-label'},String(value)));
    }
    svg.append(shape('text',{x:16,y:126,class:'ev27-axis-title'},'DI'));
    const full=milestones.map((point,i)=>x(i)+','+y(point.score)).join(' ');
    const reached=milestones.slice(0,index+1).map((point,i)=>x(i)+','+y(point.score)).join(' ');
    svg.append(shape('polyline',{points:full,class:'ev27-future-line'}));
    svg.append(shape('polyline',{points:reached,class:'ev27-main-line'}));
    milestones.forEach((point,i)=>{
      const current=i===index;
      svg.append(shape('circle',{cx:x(i),cy:y(point.score),r:current?7:4.2,class:'ev27-milestone'+(i<=index?' is-reached':'')+(current?' is-current':'')}));
      svg.append(shape('text',{x:x(i),y:y(point.score)-17,'text-anchor':'middle',class:'ev27-value'+(current?' is-current':'')},point.score.toFixed(2)));
      svg.append(shape('text',{x:x(i),y:356,'text-anchor':'middle',class:'ev27-x-label'},String(i+1).padStart(2,'0')));
    });
    return svg;
  }
  function comparison(title,from,to,kind,description) {
    const item=node('div','ev27-comparison');
    item.append(node('small','ev27-comparison-kind',kind),node('h4','',title));
    const values=node('div','ev27-comparison-values');
    values.append(node('span','',from.toFixed(2)),node('span','ev27-comparison-arrow','→'),node('strong','',to.toFixed(2)),node('small','ev27-delta','+'+(to-from).toFixed(2)+' DI'));
    item.append(values,node('p','',description));
    return item;
  }
  function render(focusKey) {
    if(destroyed)return;
    const active=document.activeElement;
    const preserved=focusKey||(host.contains(active)?active.dataset.evControl:null);
    const previousScroll=host.querySelector('.ev27-chart-scroll')?.scrollLeft ?? null;
    const point=milestones[index];
    host.classList.add('ev27');
    host.classList.toggle('is-playing',playing&&!reduced.matches);
    host.dataset.milestone=String(index);
    host.replaceChildren();
    const meta=node('div','ev27-meta');
    meta.append(node('span','','PICCOLO 27B'),node('span','',t('Full-suite Decision Index','全集 Decision Index')));
    const current=node('div','ev27-current');
    const number=node('div','ev27-current-number');
    number.append(node('strong','ev27-score',point.score.toFixed(2)),node('span','',t('from a 48.91 base','基座起点 48.91')));
    const detail=node('div','ev27-detail');
    detail.setAttribute('role','status');detail.setAttribute('aria-live',playing?'off':'polite');
    detail.append(node('small','',String(index+1).padStart(2,'0')+' / 11 · '+t(...phases[point.phase].name)),node('h3','',t(...point.title)),node('p','',t(...point.text)));
    current.append(number,detail);
    const phasePicker=node('div','ev27-phase-picker');
    phasePicker.setAttribute('role','group');phasePicker.setAttribute('aria-label',t('Exploration phase','探索阶段'));
    phases.forEach((phase,i)=>{
      const button=control(t(...phase.name),()=>select(phase.start,'phase-'+i),'phase-'+i);
      button.setAttribute('aria-pressed',String(point.phase===i));
      phasePicker.append(button);
    });
    const chartHeading=node('div','ev27-chart-heading');
    chartHeading.append(node('small','',t('Full-suite DI · higher is better','全集 DI · 越高越好')),node('span','',t('Representative checkpoints','代表性检查点')));
    const scroller=node('div','ev27-chart-scroll');
    scroller.tabIndex=0;scroller.setAttribute('aria-label',t('Scrollable evolution plot','可横向滚动的演进图'));
    scroller.append(chart());
    const scrollHint=node('p','ev27-scroll-hint',t('Swipe the chart to explore earlier checkpoints.','横向滑动图表，查看其他实验阶段。'));
    const controls=node('div','ev27-controls');
    const previous=control('←',()=>select(index-1,'previous'),'previous');
    previous.setAttribute('aria-label',t('Previous milestone','上个里程碑'));previous.disabled=index===0;
    const play=control(playing?t('Pause evolution','暂停演进'):t('Play evolution','播放演进'),()=>{
      if(playing)stop();
      else{if(index===milestones.length-1)index=0;playing=true;}
      render('play');schedule();
    },'play');
    play.setAttribute('aria-pressed',String(playing));
    const next=control('→',()=>select(index+1,'next'),'next');
    next.setAttribute('aria-label',t('Next milestone','下个里程碑'));next.disabled=index===milestones.length-1;
    controls.append(previous,play,next,node('span','ev27-current-label',t('Select an experiment below.','选择下方实验，查看对应做法。')));
    const rail=node('div','ev27-milestone-picker');
    rail.setAttribute('role','group');rail.setAttribute('aria-label',t('27B experiment milestones','27B 实验里程碑'));
    milestones.forEach((experiment,i)=>{
      const button=control(experiment.score.toFixed(2),()=>select(i,'milestone-'+i),'milestone-'+i);
      button.setAttribute('aria-pressed',String(index===i));button.title=t(...experiment.title);rail.append(button);
    });
    const comparisons=node('div','ev27-comparisons');
    comparisons.append(
      comparison(t('Reading format','读题方式'),65.05,66.19,t('SAME WEIGHTS','保持权重不变'),t('Question placement and repeated reading, evaluated with the same model weights.','在同一权重下，调整问题位置与重复阅读。')),
      comparison(t('Complementary branches','互补分支'),62.78,63.11,t('SAME EXPLORATION STAGE','同一探索阶段'),t('The strongest single branch compared with a five-branch merge.','同阶段最优单分支，与五分支合版比较。'))
    );
    host.append(meta,current,phasePicker,chartHeading,scrollHint,scroller,controls,rail,comparisons);
    if(playing||focusKey||previousScroll===null)scroller.scrollLeft=index/(milestones.length-1)*(scroller.scrollWidth-scroller.clientWidth);
    else scroller.scrollLeft=previousScroll;
    rail.scrollLeft=index/(milestones.length-1)*(rail.scrollWidth-rail.clientWidth);
    if(preserved){
      const focused=host.querySelector('[data-ev-control="'+preserved+'"]');
      (focused?.disabled?host.querySelector('[data-ev-control="play"]'):focused)?.focus({preventScroll:true});
    }
  }
  const observer=new IntersectionObserver(entries=>{
    visible=entries.some(entry=>entry.isIntersecting);
    if(!visible&&playing){stop();render();}
    else schedule();
  },{threshold:.06});
  observer.observe(host);
  const visibility=()=>{if(document.hidden&&playing){stop();render();}schedule();};
  const preference=()=>{if(reduced.matches&&playing){stop();render();}};
  document.addEventListener('visibilitychange',visibility);
  reduced.addEventListener('change',preference);
  window.addEventListener('pagehide',()=>{
    destroyed=true;stop();observer.disconnect();document.removeEventListener('visibilitychange',visibility);reduced.removeEventListener('change',preference);
  },{once:true});
  render();
  return {render};
}
