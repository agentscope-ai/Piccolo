(() => {
 const revision = new URL(document.currentScript.src).searchParams.get('v') || '9';
 const locale = window.JevI18n;
 const language = () => locale?.lang === 'zh' ? 'zh' : 'en';
 const frames = new Map();
 const labels = {harness:['Harness','Harness'],data:['Data Processing','数据处理']};
 function sync(record) {
  const lang = language(), label = labels[record.group][lang === 'zh' ? 1 : 0];
  record.frame.title = lang === 'zh' ? `${label}：六个决策场景示意` : `${label}: six illustrated decision scenarios`;
  record.frame.contentWindow?.postMessage({type:'piccolo-showcase-context',lang,
   visible:record.visible && !document.hidden},location.origin);
 }
 const observer = new IntersectionObserver(entries => {
  for (const entry of entries) {
   const record = [...frames.values()].find(item => item.frame === entry.target);
   if (record) { record.visible = entry.isIntersecting; sync(record); }
  }
 }, {threshold:0.01});
 for (const group of ['harness','data']) {
  const host = document.getElementById(`piccolo-${group}-preview`);
  if (!host) continue;
  const frame = document.createElement('iframe');
  frame.src = `./showcase/index.html?embed=1&group=${group}&lang=${language()}&v=${encodeURIComponent(revision)}`;
  frame.style.cssText = 'width:100%;height:385px;border:0;display:block;background:transparent';
  frame.loading = 'lazy';
  host.append(frame);
  const record = {frame,group,visible:false};
  frames.set(frame.contentWindow, record);
  frame.addEventListener('load', () => sync(record));
  observer.observe(frame);
  sync(record);
 }
 window.addEventListener('message', e => {
  const record = frames.get(e.source);
  if (!record || e.origin !== location.origin) return;
  if (e.data?.type === 'piccolo-showcase-height' && Number.isFinite(e.data.height)) {
   record.frame.style.height = Math.min(9000, Math.max(100, Math.ceil(e.data.height) + 5)) + 'px';
  }
 });
 locale?.onChange(() => frames.forEach(sync));
 document.addEventListener('visibilitychange', () => frames.forEach(sync));
 window.addEventListener('pagehide', () => observer.disconnect(), {once:true});
})();
