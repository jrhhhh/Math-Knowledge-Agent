(() => {
  let filter='due',items=[];
  const names={needs_review:'需要复习',hinted_complete:'依据反馈或提示完成',independent_complete:'独立完成 · 待延迟重测',stable:'稳定掌握'};
  function render() {
    const visible=items.filter(x=>filter==='all' || (filter==='wrong'?x.has_error_history:x.due));
    $('reviewList').innerHTML=visible.length?visible.map(x=>`<article class="review-card"><div><b>${escapeHtml(x.title)}</b><small>${names[x.state]}${x.pending_retest?' · 重测等待审核':''}</small></div><p>${escapeHtml(x.last_feedback || '先回忆条件和方法，再独立作答。')}</p><small>${x.first_error_step?`最近首错：第 ${x.first_error_step} 步 · `:''}复习时间：${escapeHtml(new Date(x.due_at+'Z').toLocaleString('zh-CN'))} · 已通过 ${x.independent_streak} 次间隔独立作答</small><button type="button" data-start-retest="${x.problem_id}">独立重测 ↗</button></article>`).join(''):'<div class="library-empty">暂无符合条件的记录。完成审核后会生成复习安排。</div>';
    $('reviewList').querySelectorAll('[data-start-retest]').forEach(button=>button.onclick=async()=>{
      MathPractice.clearRevision();$('practiceProblem').value=button.dataset.startRetest;$('practiceAnswer').value='';$('practiceIndependent').checked=false;
      await loadPracticeProblem();$('practiceStatus').textContent='独立重测：请先作答，暂不查看历史解答或提示。提交后仍需审核。';$('reviewWorkspace').open=false;
      document.querySelectorAll('.attempt-analysis,.attempt-review').forEach(x=>x.open=false);
      $('practiceHistory').hidden=true;
      $('practiceAnswer').focus();
    });
  }
  async function load() {
    try {
      const response=await fetch(`${API}/learning/reviews`); const data=await response.json();
      if(!response.ok) throw new Error(data.detail || '读取失败');items=data.items;
      $('reviewCounts').textContent=`${data.counts.due} 题待复习 · ${data.counts.stable} 题稳定掌握`;
      render();
    } catch(error) { $('reviewCounts').textContent='暂不可用';$('reviewList').textContent=error.message; }
  }
  document.querySelectorAll('[data-review-filter]').forEach(button=>button.onclick=()=>{filter=button.dataset.reviewFilter;document.querySelectorAll('[data-review-filter]').forEach(x=>x.setAttribute('aria-pressed',String(x===button)));render();});
  $('practiceProblem').addEventListener('change',()=>{$('practiceHistory').hidden=false;});
  $('practiceForm').addEventListener('submit',()=>{$('practiceHistory').hidden=false;});
  window.MathReview={load};load();
})();
