/* Textbook graph evidence is reviewed against the saved reading snapshot. */
(() => {
  const panel = document.getElementById('graphEvidenceReview');
  const list = document.getElementById('graphEvidenceItems');
  const progress = document.getElementById('graphEvidenceProgress');
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let candidate = null;

  function subjects(graph) {
    const names = Object.fromEntries((graph.nodes || []).map(node => [String(node.id), node.name]));
    return [
      ...(graph.nodes || []).map(node => ({type:'node', key:String(node.id), label:node.name, kind:'知识点'})),
      ...(graph.edges || []).map(edge => ({type:'edge', key:`${edge.source}->${edge.target}:${edge.relation}`, label:`${names[String(edge.source)] || edge.source} → ${names[String(edge.target)] || edge.target} · ${edge.relation}`, kind:'关系'})),
    ];
  }

  function render(data) {
    candidate = data;
    const evidence = data?.evidence || [];
    const textbook = evidence.some(item => item.context?.reading_context?.document_id);
    panel.hidden = !textbook;
    if (!textbook) return;
    const entries = subjects(data.knowledge_graph);
    const verified = entries.filter(subject => evidence.some(item => item.subject_type === subject.type && item.subject_key === subject.key && item.review_status === 'verified' && item.source_kind === 'textbook_verified')).length;
    progress.textContent = `已核对 ${verified} / ${entries.length} 项 · 保存前须逐项绑定原页摘录`;
    const reference = evidence.find(item => item.context?.reading_context?.document_id)?.context?.reading_context;
    list.innerHTML = entries.map((subject, index) => {
      const item = evidence.find(entry => entry.subject_type === subject.type && entry.subject_key === subject.key);
      const done = item?.review_status === 'verified' && item?.source_kind === 'textbook_verified';
      const page = item?.context?.source_page || item?.context?.reading_context?.start || reference?.start || 1;
      return `<article class="graph-evidence-item${done ? ' verified' : ''}" data-evidence-index="${index}">
        <div class="graph-evidence-title"><span>${escape(subject.kind)}</span><b>${escape(subject.label)}</b><em>${done ? '已核对' : '待核对'}</em></div>
        <div class="graph-evidence-fields"><label>PDF 页码 <input type="number" min="1" value="${Number(page)}" data-evidence-page></label><button type="button" data-evidence-source>打开原页</button></div>
        <textarea data-evidence-excerpt rows="2" placeholder="从本页保存文字中复制能支持这一项的原句；公式和图形请同时核对原 PDF">${done ? escape(item.excerpt) : ''}</textarea>
        <div class="graph-evidence-actions"><small>${done ? '原页摘录已保存。修改图谱后需要重新核对。' : '仅有讨论或模型推断不能视为教材证据。'}</small>${subject.type === 'edge' && data.status !== 'saved' ? '<button type="button" data-evidence-remove>无法判断，移除关系</button>' : ''}<button type="button" data-evidence-save>${done ? '更新摘录' : '确认出处'}</button></div>
      </article>`;
    }).join('');
    if (data.status === 'saved' || data.status === 'cancelled') list.querySelectorAll('[data-evidence-page],[data-evidence-excerpt],[data-evidence-save],[data-evidence-remove]').forEach(control => { control.disabled = true; });
    list.querySelectorAll('[data-evidence-index]').forEach(article => {
      const subject = entries[Number(article.dataset.evidenceIndex)];
      const pageInput = article.querySelector('[data-evidence-page]');
      article.querySelector('[data-evidence-source]').onclick = () => {
        if (!reference) return;
        window.MathWorkspace.showView('course-reader');
        window.MathCourseReader.openSource(reference.document_id, Number(pageInput.value), itemConversation(evidence));
      };
      const remove = article.querySelector('[data-evidence-remove]');
      if (remove) remove.onclick = async () => {
        if (!window.confirm(`无法确认“${subject.label}”的关系类型或方向，移除这条关系？`)) return;
        remove.disabled = true;
        try {
          const graph = structuredClone(candidate.knowledge_graph);
          graph.edges = graph.edges.filter(edge => `${edge.source}->${edge.target}:${edge.relation}` !== subject.key);
          const response = await fetch(`${window.MATH_AGENT_API || 'http://127.0.0.1:8000'}/ai/graph-candidates/${candidate.id}`, {
            method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({graph}),
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.detail || '关系移除失败');
          await window.MathGraphs.openCandidate(candidate.id);
        } catch (error) {
          article.querySelector('small').textContent = error.message;
          remove.disabled = false;
        }
      };
      article.querySelector('[data-evidence-save]').onclick = async event => {
        const button = event.currentTarget;
        button.disabled = true;
        try {
          const response = await fetch(`${window.MATH_AGENT_API || 'http://127.0.0.1:8000'}/ai/graph-candidates/${candidate.id}/textbook-evidence`, {
            method:'POST', headers:{'Content-Type':'application/json'},
            body:JSON.stringify({subject_type:subject.type, subject_key:subject.key, page:Number(pageInput.value), excerpt:article.querySelector('[data-evidence-excerpt]').value.trim()}),
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.detail || '出处核对失败');
          await window.MathGraphs.openCandidate(candidate.id);
        } catch (error) {
          article.querySelector('small').textContent = error.message;
          button.disabled = false;
        }
      };
    });
  }

  function itemConversation(evidence) {
    return evidence.find(item => item.context?.course_conversation_id)?.context.course_conversation_id;
  }

  window.MathGraphEvidenceReview = {
    render,
    clear() { candidate = null; panel.hidden = true; list.innerHTML = ''; },
    hasPending() {
      if (!candidate || panel.hidden) return false;
      return subjects(candidate.knowledge_graph).some(subject => !(candidate.evidence || []).some(item => item.subject_type === subject.type && item.subject_key === subject.key && item.review_status === 'verified' && item.source_kind === 'textbook_verified'));
    },
    open() { panel.open = true; panel.scrollIntoView({behavior:'smooth', block:'start'}); },
  };
})();
