/* Generated exercises remain editable drafts until explicitly added to practice. */
(() => {
  let concept = null;
  let selectionVersion = 0;
  let searchVersion = 0;
  let generating = false;
  const form = $('conceptExerciseForm');
  const list = $('conceptExerciseDrafts');
  const status = $('conceptExerciseStatus');
  const panel = $('conceptExercisePanel');
  let draftFilter = 'all';
  function setStatus(message, state = '') {
    status.textContent = message; status.dataset.state = state;
  }
  function updatePlan() {
    const descriptions = {基础: '定义辨析与简单实例', 应用: '条件检查与知识运用', 进阶: '证明、反例与综合推理'};
    $('conceptExercisePlan').textContent = `${concept ? concept.name + ' · ' : ''}${$('conceptExerciseCount').value} 道${$('conceptExerciseDifficulty').value}题 · ${descriptions[$('conceptExerciseDifficulty').value]}`;
  }
  $('conceptExerciseDifficulty').onchange = updatePlan;
  $('conceptExerciseCount').onchange = updatePlan;
  document.querySelectorAll('[data-exercise-goal]').forEach(button => button.onclick = () => {
    $('conceptExerciseObjective').value = button.dataset.exerciseGoal;
    document.querySelectorAll('[data-exercise-goal]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    $('conceptExerciseObjective').focus();
  });
  $('conceptExerciseObjective').oninput = () => document.querySelectorAll('[data-exercise-goal]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.exerciseGoal === $('conceptExerciseObjective').value)));
  $('practiceBackToGenerated').onclick = () => { panel.scrollIntoView({behavior: 'smooth', block: 'start'}); };

  async function request(path, method = 'GET', body) {
    const response = await fetch(`${API}/concept-exercises${path}`, {
      method, headers: {'Content-Type': 'application/json'}, ...(body ? {body: JSON.stringify(body)} : {})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '请求参数无效，请检查后重试');
    return data;
  }
  async function practice(id) {
    $('notebookQuery').value = '';
    await loadPracticeProblems();
    $('practiceProblem').value = String(id);
    await loadPracticeProblem();
    $('practiceBackToGenerated').hidden = false;
    $('practicePrompt').focus({preventScroll: true});
    $('practicePrompt').scrollIntoView({behavior: 'smooth', block: 'center'});
    $('practiceStatus').textContent = '已加入习题本，可查看思路提示与参考解答。';
  }
  function render(items) {
    list.innerHTML = items.length ? `<div class="exercise-deck-toolbar"><div><strong>${items.length} 道辅助习题</strong><small>选择一题，专注练习</small></div><div class="exercise-deck-filters" role="group" aria-label="习题筛选"><button type="button" data-draft-filter="all" aria-pressed="true">全部 ${items.length}</button><button type="button" data-draft-filter="draft" aria-pressed="false">待加入 ${items.filter(i=>!i.problem_id).length}</button><button type="button" data-draft-filter="adopted" aria-pressed="false">已加入 ${items.filter(i=>i.problem_id).length}</button></div></div><div class="exercise-deck-nav"><button type="button" data-deck-prev aria-label="上一道辅助习题">← 上一题</button><span data-deck-position aria-live="polite"></span><button type="button" data-deck-next aria-label="下一道辅助习题">下一题 →</button></div><p class="exercise-filter-empty" hidden>此分类暂无习题，试试其他分类。</p>` + items.map((item,index) => `<article class="concept-exercise-draft" data-draft="${item.id}" data-adopted="${Boolean(item.problem_id)}">
      <div class="concept-exercise-draft-head"><span>${escapeHtml(item.difficulty)} · ${item.problem_id ? '已加入习题本' : '生成草稿'}</span><small>DeepSeek 生成 · 未验证</small></div>
      <div class="exercise-card-title"><h3>${escapeHtml(item.title)}</h3></div><div id="exerciseBody${item.id}" class="exercise-card-body"><div class="concept-exercise-preview">${escapeHtml(item.content)}</div>
      <p class="concept-exercise-origin">知识点：${escapeHtml(item.context.concept.name)}${item.objective ? ` · 目标：${escapeHtml(item.objective)}` : ''}<br>${item.context.sources.length ? `参考材料：${item.context.sources.map(s => `${escapeHtml(s.document_title)} · PDF ${escapeHtml(String(s.page_start || '?'))}–${escapeHtml(String(s.page_end || s.page_start || '?'))} 页`).join('；')}（用于出题背景）` : '依据知识点描述生成，未附已审核教材片段。'} 这是辅助习题，不是原书题目。</p>
      <details class="concept-exercise-solution"><summary>查看参考解答 · 未验证</summary><div class="concept-exercise-preview">${escapeHtml(item.solution)}</div></details>
      ${item.problem_id ? '' : `<details class="concept-exercise-edit"><summary>编辑题目与解答</summary><label>标题<input data-edit-title maxlength="240" value="${escapeHtml(item.title)}"></label><label>题干<textarea data-edit-content rows="4" maxlength="12000">${escapeHtml(item.content)}</textarea></label><label>参考解答<textarea data-edit-solution rows="5" maxlength="20000">${escapeHtml(item.solution)}</textarea></label></details>`}
      <button type="button" data-adopt>${item.problem_id ? '打开习题本 ↗' : '加入习题本 ↗'}</button><span class="concept-exercise-item-status" role="status"></span></div>
    </article>`).join('') : '<div class="exercise-empty"><span>∑</span><h3>这个知识点，还缺一次练习。</h3><p>设置难度与目标，让 DeepSeek 为你生成一组习题。</p></div>';
    const cards = [...list.querySelectorAll('[data-draft]')];
    let activeCard = null;
    function focusCard(target, scroll = false) {
      activeCard = target;
      const visible = cards.filter(card => !card.hidden);
      const index = visible.indexOf(target);
      if (list.querySelector('[data-deck-position]')) {
        list.querySelector('[data-deck-position]').textContent = visible.length ? `${index >= 0 ? index + 1 : '—'} / ${visible.length}` : '0 / 0';
        list.querySelector('[data-deck-prev]').disabled = index <= 0;
        list.querySelector('[data-deck-next]').disabled = index < 0 || index >= visible.length - 1;
      }
      if (scroll && target) target.scrollIntoView({behavior: 'smooth', block: 'nearest'});
      if (target) typesetMath(target);
    }
    function filterCards(value) {
      draftFilter = value;
      cards.forEach(card => { card.hidden = value !== 'all' && (card.dataset.adopted === 'true') !== (value === 'adopted'); });
      list.querySelectorAll('[data-draft-filter]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.draftFilter === value)));
      const first = cards.find(card => !card.hidden);
      list.querySelector('.exercise-filter-empty').hidden = Boolean(first);
      focusCard(first);
    }
    list.querySelectorAll('[data-draft-filter]').forEach(button => button.onclick = () => filterCards(button.dataset.draftFilter));
    for (const [selector, delta] of [['[data-deck-prev]', -1], ['[data-deck-next]', 1]]) {
      const button = list.querySelector(selector);
      if (button) button.onclick = () => { const visible = cards.filter(card => !card.hidden); const index = visible.indexOf(activeCard); focusCard(visible[index + delta], true); };
    }
    items.forEach(item => {
      const card = list.querySelector(`[data-draft="${item.id}"]`);
      card.querySelector('[data-adopt]').onclick = async event => {
        const button = event.currentTarget;
        button.disabled = true;
        try {
          let id = item.problem_id;
          if (!id) {
            const payload = {};
            for (const key of ['title', 'content', 'solution']) payload[key] = card.querySelector(`[data-edit-${key}]`).value.trim();
            if (Object.values(payload).some(value => !value)) throw new Error('标题、题干和参考解答不能为空');
            const data = await request(`/drafts/${item.id}/adopt`, 'POST', payload);
            id = data.problem_id;
            item.problem_id = id;
            card.dataset.adopted = 'true';
            list.querySelector('[data-draft-filter="draft"]').textContent = `待加入 ${items.filter(i=>!i.problem_id).length}`;
            list.querySelector('[data-draft-filter="adopted"]').textContent = `已加入 ${items.filter(i=>i.problem_id).length}`;
            card.querySelector('.concept-exercise-draft-head span').textContent = `${item.difficulty} · 已加入习题本`;
            card.querySelector('h3').textContent = payload.title;
            card.querySelector('.concept-exercise-preview').textContent = payload.content;
            card.querySelector('.concept-exercise-solution .concept-exercise-preview').textContent = payload.solution;
            card.querySelector('.concept-exercise-edit').remove();
            typesetMath(card);
          }
          button.textContent = '打开习题本 ↗';
          await practice(id);
        } catch (error) { card.querySelector('.concept-exercise-item-status').textContent = error.message; }
        finally { button.disabled = false; }
      };
    });
    if (cards.length) filterCards(draftFilter);
    typesetMath(list);
  }
  async function select(item) {
    concept = item;
    const version = ++selectionVersion;
    ++searchVersion;
    draftFilter = 'all';
    updatePlan();
    $('conceptExerciseSelected').hidden = false;
    $('conceptExerciseSelected').textContent = `当前知识点：${item.name} · ${item.field || '数学'}`;
    $('conceptExerciseSearchResults').innerHTML = '';
    $('conceptExerciseQuery').value = item.name;
    $('conceptExerciseGenerate').disabled = generating;
    list.innerHTML = '<p class="muted">正在读取已生成的习题…</p>';
    setStatus('');
    try {
      const data = await request(`/drafts?concept_id=${encodeURIComponent(item.id)}`);
      if (version === selectionVersion) render(data.items);
    } catch (error) { if (version === selectionVersion) { list.innerHTML = ''; setStatus(error.message, 'error'); } }
  }
  $('conceptExerciseSearch').onclick = async () => {
    const version = ++searchVersion;
    const results = $('conceptExerciseSearchResults');
    results.textContent = '正在查找知识点…';
    try {
      const response = await fetch(`${API}/concepts/search?q=${encodeURIComponent($('conceptExerciseQuery').value.trim())}&limit=12`);
      const data = await response.json();
      if (!response.ok) throw new Error('知识点搜索暂不可用');
      if (version !== searchVersion) return;
      results.innerHTML = data.items.length ? data.items.map((item, index) => `<button type="button" data-pick-concept="${index}"><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.field || '数学')} · ${escapeHtml(item.type || 'concept')}</small></button>`).join('') : '<p class="muted">未找到知识点，请换个关键词。</p>';
      results.querySelectorAll('[data-pick-concept]').forEach(button => button.onclick = () => select(data.items[Number(button.dataset.pickConcept)]));
    } catch (error) { if (version === searchVersion) results.textContent = error.message; }
  };
  $('conceptExerciseQuery').onkeydown = event => {
    if (event.key === 'Enter') { event.preventDefault(); $('conceptExerciseSearch').click(); }
  };
  form.onsubmit = async event => {
    event.preventDefault();
    if (!concept || generating) return;
    const selected = concept;
    const version = selectionVersion;
    generating = true;
    const button = $('conceptExerciseGenerate');
    button.disabled = true;
    button.textContent = '正在生成…';
    const started = Date.now();
    $('conceptExerciseLoading').hidden = false;
    $('conceptExerciseElapsed').textContent = '已等待 0 秒';
    const timer = setInterval(() => { $('conceptExerciseElapsed').textContent = `已等待 ${Math.floor((Date.now()-started)/1000)} 秒`; }, 1000);
    setStatus(`正在为“${selected.name}”生成 ${$('conceptExerciseCount').value} 道习题。`);
    form.setAttribute('aria-busy', 'true');
    try {
      await request('/generate', 'POST', {concept_id: Number(selected.id), difficulty: $('conceptExerciseDifficulty').value, count: Number($('conceptExerciseCount').value), objective: $('conceptExerciseObjective').value.trim()});
      if (version !== selectionVersion) return;
      const data = await request(`/drafts?concept_id=${encodeURIComponent(selected.id)}`);
      if (version !== selectionVersion) return;
      draftFilter = 'all';
      render(data.items);
      setStatus('新习题已保存。选择一题，预览后加入习题本。', 'success');
    } catch (error) { if (version === selectionVersion) setStatus(error.message, 'error'); }
    finally {
      clearInterval(timer); $('conceptExerciseLoading').hidden = true;
      generating = false; button.disabled = !concept; button.textContent = '生成辅助习题';
      form.setAttribute('aria-busy', 'false');
    }
  };
  window.MathConceptExercises = {open(item) {
    if (!Number.isInteger(Number(item?.id)) || Number(item.id) < 1) {
      showMessage('请先保存知识点，再生成辅助习题。'); return;
    }
    $('graphConceptCard').classList.add('hidden');
    MathWorkspace.showView('practice');
    select(item);
    $('conceptExercisePanel').scrollIntoView({behavior: 'smooth', block: 'start'});
    $('conceptExerciseDifficulty').focus({preventScroll: true});
  }};
})();
