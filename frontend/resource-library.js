/* Notes and source documents share one entry; concept search belongs to the graph. */
(() => {
  let selected = 'notes';
  function highlight(tab) {
    selected = tab;
    document.querySelectorAll('[data-resource-tab]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.resourceTab === tab)));
  }
  function sync() {
    if (MathWorkspace.view === 'study-notes') highlight('notes');
    else if (MathWorkspace.view === 'knowledge-library') {
      highlight('textbooks');
      window.MathTextbooks?.list();
    }
  }
  function open(tab) {
    if (tab === 'concepts') { MathWorkspace.showView('graph'); return; }
    MathWorkspace.showView(tab === 'textbooks' ? 'knowledge-library' : 'study-notes');
  }
  document.querySelectorAll('[data-resource-tab]').forEach(button => button.onclick = () => open(button.dataset.resourceTab));
  document.addEventListener('workspacechange', sync);
  window.MathResources = {open, get tab() { return selected; }};
  sync();
})();
