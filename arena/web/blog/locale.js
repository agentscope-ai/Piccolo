/* Article and application share the same language preference and replay adapter. */
window.JevI18n = (() => {
  const listeners = new Set();
  let lang = 'en';
  try { if (localStorage.getItem('jev-language') === 'zh') lang = 'zh'; } catch {}
  const t = (en, zh) => lang === 'zh' ? (zh ?? en) : en;
  function translate(root = document) {
    root.querySelectorAll('[data-i18n-en]').forEach(node => { node.textContent = t(node.dataset.i18nEn, node.dataset.i18nZh); });
    for (const attr of ['aria-label', 'alt', 'title']) root.querySelectorAll(`[data-i18n-${attr}-en]`).forEach(node => {
      node.setAttribute(attr, t(node.getAttribute(`data-i18n-${attr}-en`), node.getAttribute(`data-i18n-${attr}-zh`)));
    });
  }
  function reflect() {
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    document.querySelectorAll('[data-language]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.language === lang)));
    translate();
  }
  function setLanguage(next, persist = true) {
    if (!['en', 'zh'].includes(next)) return;
    const changed = next !== lang;
    lang = next;
    if (persist) try { localStorage.setItem('jev-language', lang); } catch {}
    reflect();
    if (changed) for (const listener of listeners) listener(lang);
  }
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
  document.addEventListener('DOMContentLoaded', () => {
    reflect();
    document.querySelectorAll('[data-language]').forEach(button => button.addEventListener('click', () => setLanguage(button.dataset.language)));
  });
  window.addEventListener('storage', event => { if (event.key === 'jev-language') setLanguage(event.newValue === 'zh' ? 'zh' : 'en', false); });
  return {get lang() { return lang; }, t, translate, setLanguage, onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }};
})();
