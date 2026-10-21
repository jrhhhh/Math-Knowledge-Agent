/* One library entry, with existing note and textbook routes kept compatible. */
(() => {
  let selected = 'concepts';
  function highlight(tab) {
    selected = tab;
    document.querySelectorAll('[data-resource-tab]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.resourceTab === tab)));
  }
  function open(tab) {
    if (tab === 'notes') {
      MathWorkspace.showView('study-notes');
      highlight(tab);
    } else {
      MathWorkspace.showView('knowledge-library');
      document.querySelector(`[data-library-view="${tab}"]`)?.click();
      highlight(tab);
    }
  }
  document.querySelectorAll('[data-resource-tab]').forEach(button => button.onclick = () => open(button.dataset.resourceTab));
  document.querySelectorAll('[data-library-view]').forEach(button => button.addEventListener('click', () => highlight(button.dataset.libraryView)));
  document.addEventListener('workspacechange', () => {
    if (MathWorkspace.view === 'study-notes') highlight('notes');
    else if (MathWorkspace.view === 'knowledge-library') {
      highlight(document.querySelector('[data-library-view][aria-pressed="true"]')?.dataset.libraryView || 'concepts');
    }
  });
  if (MathWorkspace.view === 'study-notes') highlight('notes');
  window.MathResources = {open, get tab() { return selected; }};
})();
