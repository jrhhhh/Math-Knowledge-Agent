/* Task-based navigation. Existing panels keep their IDs and API contracts. */
(() => {
  const views = {
    ask: { title: '把难题，变成清晰的思路。', sections: ['ask', 'studyModeBar', 'responseWorkspace'] },
    'course-reader': { title: '与教材一起，走通每一步。', sections: ['course-reader'] },
    practice: { title: '生成题目，积累自己的习题本。', sections: ['practice'] },
    'knowledge-library': { title: '把知识与理解，放在一起。', sections: ['resourceHub', 'knowledge-library'] },
    'study-notes': { title: '把知识与理解，放在一起。', sections: ['resourceHub', 'study-notes'] },
    'math-lab': { title: '把抽象，变成可以观察的变化。', sections: ['math-lab'] },
    graph: { title: '看见知识之间的联系。', sections: ['graph'] },
    management: { title: '让学习空间稳定运转。', sections: ['management'] },
  };
  const descriptions = {
    explain: '讲清条件、方法和每一步依据。',
    hint: '只给一个切入点，把下一步留给你。',
    check: '带上自己的草稿，检查条件与推理缺口。',
  };
  document.querySelector('.dashboard-grid').id = 'responseWorkspace';
  const panelIds = [...new Set(Object.values(views).flatMap(view => view.sections)), 'proof'];
  let view = 'ask';
  let mode = 'explain';
  let lastQuestion = '';
  const draftKey = 'math-agent-study-draft';

  function persistDraft() {
    sessionStorage.setItem(draftKey, JSON.stringify({ question: $('question').value, proofQuestion: $('proofQuestion').value, proof: $('proofDraft').value, mode, lastQuestion }));
  }
  function showView(key, updateHash = true) {
    if (key === 'proof') { mode = 'check'; key = 'ask'; }
    if (!views[key]) key = 'ask';
    view = key;
    document.body.dataset.workspace = key;
    const visible = new Set(views[key].sections);
    if (key === 'ask' && mode === 'check') { visible.delete('ask'); visible.delete('responseWorkspace'); visible.add('proof'); }
    panelIds.forEach(id => $(id)?.classList.toggle('workspace-hidden', !visible.has(id)));
    $('workspaceTitle').textContent = views[key].title;
    document.querySelectorAll('.sidebar nav a').forEach(link => {
      const current = link.hash.slice(1) === key || (key === 'study-notes' && link.hash === '#knowledge-library');
      link.classList.toggle('active', current);
      if (current) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    });
    $('refreshGraph').classList.toggle('workspace-hidden', key !== 'graph');
    $('graphConceptCard').classList.add('hidden');
    if (updateHash && location.hash !== `#${key}`) history.pushState(null, '', `#${key}`);
    if (updateHash) window.scrollTo({ top: 0, behavior: 'instant' });
    document.querySelectorAll('[data-study-mode]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.studyMode === mode)));
    $('studyModeDescription').textContent = descriptions[mode];
    document.querySelectorAll('.flow-reveal').forEach(panel => panel.classList.add('is-flow-visible'));
    window.dispatchEvent(new Event('resize'));
    document.dispatchEvent(new CustomEvent('workspacechange', { detail: { view, mode } }));
  }
  function setMode(next) {
    if (!descriptions[next]) return;
    if (askController) { showMessage('当前回答正在生成，请等待完成或取消后再切换学习方式。'); return; }
    if (next === 'check' && !$('proofQuestion').value.trim()) $('proofQuestion').value = $('question').value.trim() || lastQuestion || [...document.querySelectorAll('#chatTimeline .chat-message.user .chat-bubble')].at(-1)?.textContent || '';
    if (mode === 'check' && !$('question').value.trim()) $('question').value = $('proofQuestion').value.trim();
    mode = next;
    $('question').placeholder = mode === 'hint' ? '输入题目或卡住的那一步，我只给提示…' : '输入题目、继续追问，或针对某一步展开…';
    persistDraft();
    showView('ask');
    (mode === 'check' ? $('proofDraft') : $('question')).focus({ preventScroll: true });
  }
  window.MathWorkspace = {
    get mode() { return mode; },
    get view() { return view; },
    showView, setMode,
    rememberQuestion(question) { lastQuestion = question; persistDraft(); },
    restoreContext(messages) {
      const latest = [...messages].reverse().find(message => message.role === 'user');
      lastQuestion = latest?.content || '';
    },
  };
  document.querySelectorAll('[data-study-mode]').forEach(button => button.addEventListener('click', () => setMode(button.dataset.studyMode)));
  ['question', 'proofQuestion', 'proofDraft'].forEach(id => $(id).addEventListener('input', persistDraft));
  document.querySelectorAll('.sidebar nav a').forEach(link => link.addEventListener('click', event => { event.preventDefault(); showView(link.hash.slice(1)); }));
  window.addEventListener('hashchange', () => showView(location.hash.slice(1), false));
  window.addEventListener('popstate', () => showView(location.hash.slice(1), false));
  $('practiceToStudy').addEventListener('click', async () => {
    if (askController) { showMessage('当前回答正在生成，请等待完成或取消后再带入练习。'); return; }
    const selectedId = $('practiceProblem').value;
    if (!selectedId) return;
    const response = await fetch(`${API}/problems/`);
    if (!response.ok) { showMessage('题目读取失败，请稍后重试。'); return; }
    const problem = (await response.json()).find(item => String(item.id) === selectedId);
    if (!problem) return;
    lastQuestion = problem.content;
    $('question').value = problem.content;
    $('proofQuestion').value = problem.content;
    setMode('hint');
  });
  $('utilityDrawer').open = true;
  const observer = new MutationObserver(() => {
    document.querySelectorAll('#graph > details.retry-jobs').forEach(panel => $('utilityDrawer').querySelector('.utility-grid').appendChild(panel));
  });
  observer.observe($('graph'), { childList: true });
  try {
    const draft = JSON.parse(sessionStorage.getItem(draftKey) || '{}');
    $('question').value = draft.question || '';
    $('proofQuestion').value = draft.proofQuestion || '';
    $('proofDraft').value = draft.proof || '';
    mode = descriptions[draft.mode] ? draft.mode : 'explain';
    lastQuestion = draft.lastQuestion || '';
  } catch (_) { /* A damaged draft never blocks the workspace. */ }
  showView(location.hash.slice(1) || 'ask', false);
  fetch(`${API}/`).then(response => { $('workspaceConnection').textContent = response.ok ? '服务在线' : '服务异常'; }).catch(() => { $('workspaceConnection').textContent = '连接中断'; });
})();
