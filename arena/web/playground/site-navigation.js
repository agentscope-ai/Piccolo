/* Geometry stays fixed. Motion is restricted to labels, glass decoration and opacity. */
(function () {
  'use strict';
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const animations=new Set(),slots=new Map();
  function motion(node,frames,options,slot='main'){
    if(!node||reduced.matches||document.hidden)return;
    const group=slots.get(node)||new Map();group.get(slot)?.cancel();
    const animation=node.animate(frames,options);group.set(slot,animation);slots.set(node,group);animations.add(animation);
    const clear=()=>{animations.delete(animation);if(group.get(slot)===animation)group.delete(slot);if(!group.size&&slots.get(node)===group)slots.delete(node);};
    animation.finished.then(clear,clear);return animation;
  }
  function cancelAll(){for(const animation of animations)animation.cancel();animations.clear();slots.clear();window.BlinkDust?.cancel();}
  function reveal(node){motion(node,[{opacity:.5},{opacity:1}],{duration:200,easing:'cubic-bezier(.2,.7,.3,1)'});}
  function pageText(){return [document.getElementById('sitePageContent')].filter(Boolean);}
  function intro(view,direction=1,delay=60){
    // One paint group covers everything below the stationary glass tabs,
    // including canvases, iframe worlds, controls and the footer.
    for(const node of pageText())if(!window.BlinkDust?.reveal(node,direction,delay))reveal(node);
  }
  intro(document.querySelector('.tabs button.active')?.dataset.tab||'blog',1,80);
  let gameTimer=0;
  function gameIntro(){clearTimeout(gameTimer);gameTimer=setTimeout(()=>{gameTimer=0;if(!document.getElementById('gamesView')?.classList.contains('hidden')){cancelAll();intro('games',1,0);}},120);}
  // Picker navigation may scroll the page. Wait until that movement settles
  // before sampling, so the full game is included without stale positions.
  window.addEventListener('blink:game-ready',gameIntro);
  window.addEventListener('scroll',()=>{if(gameTimer)gameIntro();},{passive:true});
  for(const [selector,primary] of [['.tabs',true],['#leaderboardTabs',false]]){
    const nav=document.querySelector(selector);if(!nav)continue;
    let frame=0,last=null;
    if(primary)nav.addEventListener('click',event=>{
      const target=event.target.closest('button[data-tab]'),current=nav.querySelector('button.active');
      if(!target||!current||target===current)return;
      const buttons=[...nav.querySelectorAll('button')],direction=buttons.indexOf(target)>buttons.indexOf(current)?1:-1;
      // Capture outgoing content while it still has layout, before app.js hides the old page.
      cancelAll();for(const node of pageText(current.dataset.tab))window.BlinkDust?.dissolve(node,direction);
    },true);
    const indicatorClass=primary?'nav-glass':'nav-underline';
    nav.setAttribute('role','tablist');if(primary)nav.setAttribute('aria-label','Blink');
    function reflect(){
      frame=0;const selected=nav.querySelector('button.active');if(!selected||!nav.getClientRects().length)return;
      const buttons=[...nav.querySelectorAll('button')];
      for(const button of buttons){
        button.setAttribute('role','tab');button.setAttribute('aria-selected',String(button===selected));button.tabIndex=button===selected?0:-1;
        if(primary)button.setAttribute('aria-controls',({blog:'blogView',games:'gamesView',leaderboard:'leaderboardView'})[button.dataset.tab]);
      }
      let indicator=nav.querySelector('.'+indicatorClass);const fresh=!indicator;
      if(!indicator){
        indicator=document.createElement('span');indicator.className=indicatorClass;indicator.setAttribute('aria-hidden','true');
        if(primary){const light=document.createElement('span');light.className='nav-wind-light';indicator.appendChild(light);}
        nav.appendChild(indicator);
      }
      const x=selected.offsetLeft+(primary?0:12),y=primary?selected.offsetTop:selected.offsetTop+selected.offsetHeight-2;
      if(fresh)indicator.style.transition='none';
      indicator.style.width=(selected.offsetWidth-(primary?0:24))+'px';indicator.style.height=(primary?selected.offsetHeight:2)+'px';
      indicator.style.transform='translate3d('+x+'px,'+y+'px,0)';
      if(fresh)requestAnimationFrame(()=>{indicator.style.transition='';});
      if(last&&last!==selected){
        if(primary){
          const direction=buttons.indexOf(selected)>buttons.indexOf(last)?1:-1;
          intro(selected.dataset.tab,direction);
          motion(indicator.querySelector('.nav-wind-light'),[{opacity:0,transform:'translateX('+(-direction*100)+'%)'},{opacity:.8,offset:.35},{opacity:0,transform:'translateX('+(direction*100)+'%)'}],{duration:550,easing:'ease-out'});
          if(!reduced.matches&&!document.hidden){const box=selected.getBoundingClientRect();window.dispatchEvent(new CustomEvent('blink:wind',{detail:{x:box.x+box.width/2,y:box.y+box.height/2,direction}}));}
        }else reveal(document.getElementById('leaderboardDetail'));
        const left=selected.offsetLeft,right=left+selected.offsetWidth;
        if(left<nav.scrollLeft||right>nav.scrollLeft+nav.clientWidth)nav.scrollTo({left:Math.max(0,left-(nav.clientWidth-selected.offsetWidth)/2),behavior:reduced.matches?'instant':'smooth'});
      }
      last=selected;
    }
    function schedule(){if(!frame)frame=requestAnimationFrame(reflect);}
    new MutationObserver(schedule).observe(nav,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
    new ResizeObserver(schedule).observe(nav);document.fonts.ready.then(schedule);window.JevI18n?.onChange(schedule);
    nav.addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      const buttons=[...nav.querySelectorAll('button')],index=buttons.indexOf(event.target);if(index<0)return;
      const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;
      event.preventDefault();buttons[next].focus({preventScroll:true});buttons[next].click();
    });schedule();
  }
  document.addEventListener('pointerdown',event=>{const picker=document.querySelector('.lb-model-picker[open]');if(picker&&!picker.contains(event.target))picker.open=false;},{passive:true});
  document.addEventListener('keydown',event=>{if(event.key!=='Escape')return;const picker=document.querySelector('.lb-model-picker[open]');if(picker){picker.open=false;picker.querySelector('summary').focus({preventScroll:true});}});
  reduced.addEventListener('change',()=>{if(reduced.matches)cancelAll();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)cancelAll();});
  window.addEventListener('resize',cancelAll,{passive:true});
  window.addEventListener('scroll',cancelAll,{passive:true});
  window.JevI18n?.onChange(cancelAll);
})();
