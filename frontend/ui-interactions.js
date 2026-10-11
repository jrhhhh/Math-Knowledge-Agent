/* Decorative CSS icons: never replace labels, IDs, handlers, or inner content. */
(() => {
  const rules = {
    '.sidebar a[href="#ask"]':'chat','.sidebar a[href="#practice"]':'pen','.sidebar a[href="#knowledge-library"]':'library','.sidebar a[href="#study-notes"]':'file','.sidebar a[href="#graph"]':'graph','.sidebar a[href="#math-lab"]':'flask','.sidebar a[href="#management"]':'settings',
    '[data-study-mode="explain"]':'book','[data-study-mode="hint"]':'bulb','[data-study-mode="check"]':'check',
    '#askButton':'send','#renameConversation':'pen','#saveAnswerNote':'save','#saveGraphButton':'check','#refreshGraph':'refresh',
    '#openTextbookImport':'upload','#previewReaderMath':'eye','#saveChunkReview':'save','#saveDocumentReview':'check','#askReadingSelection':'chat','#originalPdfLink':'file',
    '#refreshLearningMetrics':'refresh','#exportLearningMetrics':'download','#labReset':'refresh','#labToStudy':'chat',
    '[data-lab-mode="derivative"]':'curve','[data-lab-mode="integral"]':'chart','[data-lab-mode="linear"]':'grid',
    '[data-library-view="concepts"]':'bulb','[data-library-view="textbooks"]':'book',
    '#practiceToStudy':'chat','[data-attempt-analyze]':'check','[data-attempt-revise]':'pen','[data-attempt-next]':'arrow','[data-review-submit]':'save','[data-start-retest]':'refresh',
    '[data-note-edit]':'pen','[data-note-favorite]':'star','[data-note-archive]':'archive','.note-actions a[download]':'download',
    '#newNote':'plus','#saveNoteEdit':'save',
    '.attempt-review > summary':'check','.attempt-analysis > summary':'check','#learningMetrics > summary':'chart','.step-evidence > summary':'file','.document-review > summary':'book','#graphHistory > summary':'clock',
  };
  function decorate(scope=document) {
    if(scope!==document && !scope.matches?.("button,a,summary") && !scope.querySelector?.("button,a,summary"))return;
    for(const [selector,icon] of Object.entries(rules)) {
      if(scope.matches?.(selector))scope.dataset.uiIcon=icon;
      scope.querySelectorAll?.(selector).forEach(el=>{if(el.dataset.uiIcon!==icon)el.dataset.uiIcon=icon;});
    }
  }
  decorate();
  // Observe inserted cards only. Setting data attributes never triggers this observer.
  new MutationObserver(records=>{
    for(const record of records)for(const node of record.addedNodes)if(node.nodeType===1)decorate(node);
  }).observe(document.querySelector('.main-content'),{childList:true,subtree:true});
})();
