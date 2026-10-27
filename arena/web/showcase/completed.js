/* Small bilingual shell; the replay component shares the Arena i18n contract. */
(() => {
  const listeners = new Set();
  const requested = new URLSearchParams(location.search).get('lang');
  window.JevI18n = {
    lang: requested === 'zh' ? 'zh' : 'en',
    t(en, zh) { return this.lang === 'zh' ? (zh ?? en) : en; },
    onChange(callback) { listeners.add(callback); },
    register() {},
  };
  function select(lang) {
    window.JevI18n.lang = lang;
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    document.querySelectorAll('[data-en]').forEach(node => {
      node.textContent = node.dataset[lang];
    });
    document.querySelectorAll('[data-language]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.language === lang));
    });
    listeners.forEach(callback => callback());
  }
  document.querySelectorAll('[data-language]').forEach(button => {
    button.addEventListener('click', () => select(button.dataset.language));
  });
  select(window.JevI18n.lang);
})();
