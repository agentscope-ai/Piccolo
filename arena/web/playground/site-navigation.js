/* Stable publication navigation: semantic tabs and a short opacity transition. */
(function () {
  'use strict';
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const animations=new Map();
  function cancelAll(){
    for(const animation of animations.values())animation.cancel();
    animations.clear();
  }
  function reveal(node){
    if(!node||reduced.matches||document.hidden||typeof node.animate!=='function')return;
    animations.get(node)?.cancel();
    const animation=node.animate([{opacity:.65},{opacity:1}],{duration:180,easing:'ease-out'});
    animations.set(node,animation);
    const clear=()=>{if(animations.get(node)===animation)animations.delete(node);};
    animation.finished.then(clear,clear);
  }
  for(const [selector,primary] of [['.tabs',true],['#leaderboardTabs',false]]){
    const nav=document.querySelector(selector);if(!nav)continue;
    let frame=0,last=null;
    nav.setAttribute('role','tablist');
    if(primary)nav.setAttribute('aria-label','Piccolo');
    function reflect(){
      frame=0;
      const selected=nav.querySelector('button.active');
      if(!selected)return;
      const buttons=[...nav.querySelectorAll('button')];
      for(const button of buttons){
        button.setAttribute('role','tab');
        button.setAttribute('aria-selected',String(button===selected));
        button.tabIndex=button===selected?0:-1;
        if(primary){
          const panel=({blog:'blogView',games:'gamesView',leaderboard:'leaderboardView'})[button.dataset.tab];
          if(panel){
            button.id='tab-'+button.dataset.tab;
            button.setAttribute('aria-controls',panel);
            const content=document.getElementById(panel);
            content?.setAttribute('role','tabpanel');
            content?.setAttribute('aria-labelledby',button.id);
          }
        }
      }
      if(last&&last!==selected){
        cancelAll();
        reveal(document.getElementById(primary?'sitePageContent':'leaderboardDetail'));
        // Only the horizontally scrollable benchmark row may scroll; the page stays in place.
        if(!primary&&nav.getClientRects().length){
          const left=selected.offsetLeft,right=left+selected.offsetWidth;
          if(left<nav.scrollLeft||right>nav.scrollLeft+nav.clientWidth){
            nav.scrollLeft=Math.max(0,left-(nav.clientWidth-selected.offsetWidth)/2);
          }
        }
      }
      last=selected;
    }
    function schedule(){if(!frame)frame=requestAnimationFrame(reflect);}
    new MutationObserver(schedule).observe(nav,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
    new ResizeObserver(schedule).observe(nav);
    document.fonts.ready.then(schedule);
    window.JevI18n?.onChange(schedule);
    nav.addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      const buttons=[...nav.querySelectorAll('button')],index=buttons.indexOf(event.target);
      if(index<0)return;
      const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;
      event.preventDefault();
      buttons[next].focus({preventScroll:true});
      buttons[next].click();
    });
    schedule();
  }
  document.addEventListener('pointerdown',event=>{
    const picker=document.querySelector('.lb-model-picker[open]');
    if(picker&&!picker.contains(event.target))picker.open=false;
  },{passive:true});
  document.addEventListener('keydown',event=>{
    if(event.key!=='Escape')return;
    const picker=document.querySelector('.lb-model-picker[open]');
    if(picker){
      picker.open=false;
      picker.querySelector('summary').focus({preventScroll:true});
    }
  });
  reduced.addEventListener('change',()=>{if(reduced.matches)cancelAll();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)cancelAll();});
  window.addEventListener('oneshot:game-ready',cancelAll);
  window.addEventListener('resize',cancelAll,{passive:true});
  window.JevI18n?.onChange(cancelAll);
})();
