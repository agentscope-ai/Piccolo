(function () {
  'use strict';
  const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function markup(value) {
    if(typeof value!=='string'||!value||/[\s\\\u0000-\u001f]/.test(value)||value.startsWith('//'))return '';
    try {
      const url=new URL(value,document.baseURI);
      if(!['http:','https:'].includes(url.protocol)||url.username||url.password)return '';
    } catch {return '';}
    return '<img class="lb-model-logo" src="'+escape(value)+'" width="20" height="20" alt="" decoding="async" referrerpolicy="no-referrer">';
  }
  // A missing optional asset leaves the name intact, without a broken-image box.
  document.addEventListener('error',event=>{
    if(event.target instanceof HTMLImageElement&&event.target.classList.contains('lb-model-logo'))event.target.hidden=true;
  },true);
  window.JevModelLogo={markup};
})();
