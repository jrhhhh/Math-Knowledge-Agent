/* Reviewed attempts retain their drafts; machine analysis never grants correctness. */
(() => {
  let parentId = null;
  const names = {unverified:'等待人工审核',correct:'审核：正确',partially_correct:'审核：部分正确',incorrect:'审核：错误'};
  const errors = {missing_assumption:'条件缺失',invalid_inference:'推理缺口',wrong_theorem:'定理使用不当',incomplete:'过程不完整',undefined_symbol:'符号未定义',circular_reasoning:'循环论证'};
  async function request(path, method, body) {
    const response = await fetch(`${API}${path}`, {method,headers:{'Content-Type':'application/json'}, ...(body?{body:JSON.stringify(body)}:{})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '请求失败');
    return data;
  }
  function clearRevision() { parentId = null; $('practiceRevision').hidden = true; }
  function revise(item) {
    parentId = item.id;
    $('practiceAnswer').value = item.answer;
    $('practiceIndependent').checked = false;
    $('practiceRevision').hidden = false;
    $('practiceRevision').innerHTML = `正在修订作答 #${item.id}；提交将保留原记录。 <button type="button" id="cancelRevision">取消修订</button>`;
    $('cancelRevision').onclick = clearRevision;
    $('practiceAnswer').focus();
    $('practiceStatus').textContent = item.first_error_step ? `从第 ${item.first_error_step} 步开始修改：${item.feedback || '核对条件与推理依据'}` : `依据反馈修订：${item.feedback || '先核对条件，再补齐推导'}`;
  }
  function analysisMarkup(data) {
    if (!data) return '';
    const local = data.review_source === 'local_rule_fallback';
    const first = (data.steps || []).find(step=>step.status!=='valid' && step.error_type!=='none');
    return `<details class="attempt-analysis"><summary>${local?'结构检查':'模型辅助检查'} · 不代替人工判断</summary><p>${escapeHtml(data.summary || '')}</p>${first?`<p><b>首个需核对：第 ${Number(first.step)} 步</b> ${escapeHtml(first.reason || '')}</p>`:''}${(data.steps || []).map(step=>`<div><b>步骤 ${Number(step.step)} · ${escapeHtml(errors[step.error_type] || '未标记错误')}</b><p>${escapeHtml(step.text)}</p><small>${escapeHtml(step.reason)}</small></div>`).join('')}<small>辅助检查不会自动更新正确性或掌握状态。</small></details>`;
  }
  function render(items) {
    $('practiceHistory').innerHTML = items.length ? items.map(item => `<article class="practice-attempt" data-attempt="${item.id}"><div class="attempt-heading"><b>${names[item.correctness] || '等待审核'}</b><small>#${item.id}${item.parent_attempt_id?` · 修订自 #${item.parent_attempt_id}`:''} · ${escapeHtml((item.created_at || '').replace('T',' ').slice(0,16))}</small></div><p class="attempt-draft">${escapeHtml(item.answer)}</p>${item.first_error_step?`<p class="attempt-error">首错：第 ${item.first_error_step} 步 · ${escapeHtml(errors[item.error_type] || '推理需修改')}</p>`:''}<p class="attempt-feedback">${escapeHtml(item.feedback || '尚无人工审核反馈。可先获取辅助检查，再由审核者确认。')}</p>${analysisMarkup(item.analysis)}<div class="attempt-actions"><button type="button" data-attempt-analyze>辅助检查</button><button type="button" data-attempt-revise>修订重交</button>${item.correctness !== 'unverified'?'<button type="button" data-attempt-next>下一步练习</button>':''}</div><details class="attempt-review"><summary>审核工作区 · 人工确认</summary><p class="muted">仅由能判断解答正确性的审核者填写；尚不确定时保持“未判断”。</p><label>正确性<select data-review-correctness aria-label="审核正确性"><option value="unverified">未判断</option><option value="correct">正确</option><option value="partially_correct">部分正确</option><option value="incorrect">错误</option></select></label><label>首错步骤<input data-review-step type="number" min="1" aria-label="首错步骤"></label><label>错误类型<select data-review-error aria-label="错误类型"><option value="">未标记</option>${Object.entries(errors).map(([value,label])=>`<option value="${value}">${label}</option>`).join('')}</select></label><label>反馈与下一步<textarea data-review-feedback aria-label="审核反馈" placeholder="指出需要修改的步骤及具体训练动作"></textarea></label><label><input data-review-independent type="checkbox" ${item.independent==='yes'?'checked':''} ${item.hint_level?'disabled':''}> 无提示独立完成</label><button type="button" data-review-submit>保存人工审核</button></details></article>`).join('') : '<div class="library-empty">提交一次作答，开始反馈与修订。</div>';
    items.forEach(item => {
      const card = document.querySelector(`[data-attempt="${item.id}"]`);
      card.querySelector('[data-review-correctness]').value = item.correctness;
      card.querySelector('[data-review-step]').value = item.first_error_step || '';
      card.querySelector('[data-review-error]').value = item.error_type || '';
      card.querySelector('[data-review-feedback]').value = item.feedback || '';
      card.querySelector('[data-attempt-revise]').onclick = ()=>revise(item);
      card.querySelector('[data-attempt-analyze]').onclick = async (event)=>{
        event.target.disabled=true; event.target.textContent='检查中…';
        try { await request(`/problems/attempts/${item.id}/analyze`,'POST'); await loadPracticeProblem(); $('practiceStatus').textContent='辅助检查已保存；正确性仍由人工审核确认。'; }
        catch(error) { $('practiceStatus').textContent=error.message; event.target.disabled=false; event.target.textContent='辅助检查'; }
      };
      card.querySelector('[data-review-submit]').onclick=async(event)=>{
        event.target.disabled=true;
        const step=card.querySelector('[data-review-step]').value;
        try {
          const data=await request(`/problems/attempts/${item.id}/review`,'PUT',{correctness:card.querySelector('[data-review-correctness]').value,first_error_step:step?Number(step):null,error_type:card.querySelector('[data-review-error]').value || null,feedback:card.querySelector('[data-review-feedback]').value.trim() || null,independent:card.querySelector('[data-review-independent]').checked && !item.hint_level});
          await loadPracticeProblem();
          const remediation=data.learning_update?.remediation || [];
          $('practiceStatus').textContent=`人工审核已保存。${remediation.length?`建议补学：${remediation.map(x=>x.name).join('、')}`:data.correctness==='correct'?'可继续练习，并安排延迟重测。':'请根据反馈修订重交。'}`;
          loadLearningPulse();
        } catch(error) { $('practiceStatus').textContent=error.message; event.target.disabled=false; }
      };
      const next=card.querySelector('[data-attempt-next]');
      if(next) next.onclick=async()=>{
        try {
          const data=await request(`/problems/next?problem_id=${item.problem_id}`,'GET');
          if(!data.item) throw new Error(data.reason);
          clearRevision(); $('practiceAnswer').value=''; $('practiceProblem').value=String(data.item.id); await loadPracticeProblem(); $('practiceStatus').textContent=data.reason;
        } catch(error) { $('practiceStatus').textContent=error.message; }
      };
    });
    typesetMath($('practiceHistory'));
  }
  $('practiceProblem').addEventListener('change',()=>{clearRevision();$('practiceAnswer').value='';});
  window.MathPractice={render,clearRevision,get parentId(){return parentId;}};
})();
