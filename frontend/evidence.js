/* Inspect evidence without leaving the current mathematical discussion. */
(() => {
  let current = null;
  const labels = {
    scoped_calculation: '受限精确计算', tool_scope: '工具方法与范围',
    source_cited: '已引用教材 · 仍需核对推理', unverified: '尚未验证', teaching_hint: '教学提示',
  };
  const dialog = document.createElement('dialog');
  dialog.id = 'evidenceDialog';
  dialog.className = 'evidence-dialog';
  dialog.setAttribute('aria-labelledby', 'evidenceDialogTitle');
  dialog.innerHTML = '<header><span class="section-label">EVIDENCE</span><button type="button" aria-label="关闭依据详情">×</button></header><h2 id="evidenceDialogTitle"></h2><div id="evidenceDialogBody"></div>';
  document.body.appendChild(dialog);
  dialog.querySelector('button').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });

  function openSource(chunkId) {
    const source = (current?.knowledge_sources || []).find(item => String(item.chunk_id) === String(chunkId));
    if (!source) return;
    $('evidenceDialogTitle').textContent = source.document_title || '教材片段';
    $('evidenceDialogBody').innerHTML = `<p class="evidence-caption">${escapeHtml(source.course || '')} · ${escapeHtml(source.chapter || '未分章')} · 第 ${escapeHtml(String(source.page_start || '?'))} 页</p><p class="evidence-boundary">这是回答引用的已审核资料。请核对它是否支持当前推理，以及必要条件是否满足。</p><div class="evidence-original">${escapeHtml(source.content || '')}</div>`;
    dialog.showModal();
    typesetMath($('evidenceDialogBody'));
  }
  function openTool(toolId) {
    const tool = current?.agent_tool_evidence?.[Number(toolId) - 1];
    if (!tool) return;
    const names = { symbolic_derivative: '多项式求导', exact_definite_integral: '多项式定积分', polynomial_identity: '多项式恒等式检查', computed: '精确算术' };
    $('evidenceDialogTitle').textContent = names[tool.evidence_type] || '工具执行证据';
    const input = tool.evidence_type === 'polynomial_identity' ? `${tool.left} = ${tool.right}` : tool.expression || tool.theorem || '';
    const result = tool.evidence_type === 'symbolic_derivative' ? formatAgentPolynomial(tool.derivative)
      : tool.evidence_type === 'polynomial_identity' ? `${tool.identity ? '恒等式成立' : '不是恒等式'}；左侧减右侧：${tool.difference}`
      : tool.value != null ? String(tool.value) : tool.detail || tool.status;
    $('evidenceDialogBody').innerHTML = `<dl><dt>实际输入</dt><dd>${escapeHtml(input)}</dd>${tool.lower != null ? `<dt>积分上下限</dt><dd>${escapeHtml(String(tool.lower))} → ${escapeHtml(String(tool.upper))}</dd>` : ''}<dt>计算结果</dt><dd>${escapeHtml(result)}</dd><dt>方法</dt><dd>${escapeHtml(tool.method || tool.tool_name || '本地受控工具')}</dd>${tool.tool_version ? `<dt>工具版本</dt><dd>${escapeHtml(tool.tool_version)}</dd>` : ''}</dl><p class="evidence-boundary">${escapeHtml(tool.assumptions || '仅支持该工具实际处理的输入，不代表完整回答已获证明。')}</p>`;
    dialog.showModal();
  }
  function render(data) {
    current = data;
    let panel = $('answerStepEvidence');
    if (!panel) {
      panel = document.createElement('details');
      panel.id = 'answerStepEvidence';
      panel.className = 'answer-sources step-evidence';
      $('answer').parentElement.appendChild(panel);
    }
    const steps = data?.answer_steps || [];
    if (!steps.length) {
      panel.innerHTML = '<summary>逐步依据 · 暂无映射记录</summary><p class="muted">这份回答没有保存逐步引用。已有来源可在教材出处中查看，不能据此推断每一步都获得验证。</p>';
      return;
    }
    panel.innerHTML = `<summary>逐步依据 · ${steps.length} 段</summary><p class="evidence-boundary">引用说明资料来源；计算只验证对应对象。其余推理仍需核对。</p>${steps.map(step => `<article class="evidence-step"><div class="evidence-step-head"><b>${escapeHtml(String(step.step)).padStart(2, '0')}</b><span class="evidence-state evidence-${escapeHtml(step.status)}">${labels[step.status] || '尚未验证'}</span></div><p>${escapeHtml(step.text)}</p><div class="evidence-links">${(step.source_chunk_ids || []).map(id => `<button type="button" data-evidence-source="${Number(id)}">教材 S${Number(id)} ↗</button>`).join('')}${(step.tool_ids || []).map(id => `<button type="button" data-evidence-tool="${Number(id)}">查看计算依据 ↗</button>`).join('')}</div>${(step.unresolved_citations || []).length ? `<small class="evidence-warning">未提供对应来源：${step.unresolved_citations.map(escapeHtml).join('、')}</small>` : ''}</article>`).join('')}`;
    panel.querySelectorAll('[data-evidence-source]').forEach(button => button.addEventListener('click', () => openSource(button.dataset.evidenceSource)));
    panel.querySelectorAll('[data-evidence-tool]').forEach(button => button.addEventListener('click', () => openTool(button.dataset.evidenceTool)));
    typesetMath(panel);
  }
  window.MathEvidence = { render, openSource, openTool };
  if (lastAskResult) render(lastAskResult);
})();
