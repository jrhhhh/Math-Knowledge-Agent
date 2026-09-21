const API = window.MATH_AGENT_API || 'http://127.0.0.1:8000';
const $ = (id) => document.getElementById(id);
let adminKey = sessionStorage.getItem('math-agent-admin-key') || '';
let adminToken = sessionStorage.getItem('math-agent-admin-token') || '';
const nativeFetch = window.fetch.bind(window);
window.fetch = (input, init = {}) => { const method = String(init.method || 'GET').toUpperCase(); if ((adminKey || adminToken) && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) { const headers = new Headers(init.headers || {}); if (adminToken) headers.set('Authorization', `Bearer ${adminToken}`); else headers.set('X-Admin-Key', adminKey); init = { ...init, headers }; } return nativeFetch(input, init); };
let activeCandidateId = null;
let askController = null;
let lastAiErrorCode = null;
let lastAskResult = null;
let lastAskRequestId = null;
let lastSecurityAlertSignature = '';
let activeGraphContext = { nodes: [], edges: [] };
const trackedFetch = window.fetch;
window.fetch = (input, init = {}) => {
  const url = typeof input === 'string' ? input : input?.url || '';
  const match = url.match(/\/ai\/ask-stream\?request_id=([^&]+)/);
  if (match) lastAskRequestId = decodeURIComponent(match[1]);
  return trackedFetch(input, init);
};
function notifySecurityAlerts(alerts) { if (!alerts?.length || !window.Notification || Notification.permission !== 'granted') return; const signature = alerts.map(item => `${item.type}:${item.ip_address || ''}:${item.count}`).join('|'); if (signature === lastSecurityAlertSignature) return; lastSecurityAlertSignature = signature; new Notification('Math Agent 安全告警', { body: alerts.map(item => item.message).join('；') }); }
function ensureAdminPanel() { if ($('adminPanel')) return; const panel = document.createElement('details'); panel.id = 'adminPanel'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>管理权限</summary><div class="template-preview"><input id="adminKeyInput" type="password" placeholder="输入管理员密钥（仅当前会话）" aria-label="管理员密钥"><button type="button" id="saveAdminKey">登录</button><button type="button" id="clearAdminKey">清除</button><output id="adminKeyStatus"></output></div>'; $('graph').appendChild(panel); $('adminKeyInput').value = adminKey; $('saveAdminKey').onclick = async () => { const key = $('adminKeyInput').value.trim(); if (!key) { $('adminKeyStatus').textContent = '请输入密钥'; return; } try { const response = await nativeFetch(`${API}/ai/auth/login`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({key})}); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '登录失败'); adminKey = key; adminToken = data.access_token; sessionStorage.setItem('math-agent-admin-key', adminKey); sessionStorage.setItem('math-agent-admin-token', adminToken); $('adminKeyStatus').textContent = '登录成功，token 有效 1 小时'; } catch (error) { adminToken = ''; sessionStorage.removeItem('math-agent-admin-token'); $('adminKeyStatus').textContent = error.message; } }; $('clearAdminKey').onclick = () => { adminKey = ''; adminToken = ''; sessionStorage.removeItem('math-agent-admin-key'); sessionStorage.removeItem('math-agent-admin-token'); $('adminKeyInput').value = ''; $('adminKeyStatus').textContent = '已清除'; }; }
const typeColor = { concept: '#55d8ff', theorem: '#ffcb68', property: '#bc8cff', method: '#77f2ad' };

function showMessage(text) { const hints = { timeout: '模型响应超时，请稍后重新提交。', rate_limit: '请求较频繁，请等待片刻后重试。', network: '请检查网络或后端服务是否在线。', server_error: '模型服务暂时异常，后台会继续重试。', invalid_response: '模型返回格式异常，请重新生成。' }; const inferred = text.includes('超时') ? 'timeout' : text.includes('频繁') || text.includes('限流') ? 'rate_limit' : text.includes('连接') || text.includes('网络') ? 'network' : text.includes('格式') ? 'invalid_response' : lastAiErrorCode; const hint = Object.prototype.hasOwnProperty.call(hints, inferred) ? ` ${hints[inferred]}` : ''; $('message').textContent = `${text}${hint}`; $('message').classList.remove('hidden'); }
function clearMessage() { $('message').classList.add('hidden'); }
function typesetMath(element) { if (window.MathJax?.typesetPromise) window.MathJax.typesetPromise([element]).then(() => { if (element.id === 'answer' && /\\\(|\\\[|\$/.test(element.textContent) && !element.querySelector('.mjx-container')) showMathRenderError(element); }).catch(() => { showMathRenderError(element); }); }
function showMathRenderError(element) { if (element.id !== 'answer' || $('mathRenderError')) return; const panel = document.createElement('details'); panel.id = 'mathRenderError'; panel.className = 'formula-fixes'; panel.innerHTML = '<summary>公式渲染失败，查看原始文本</summary><pre></pre>'; panel.querySelector('pre').textContent = element.textContent || ''; element.appendChild(panel); }
function escapeHtml(s = '') { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function renderConcepts(items = []) { $('conceptCount').textContent = items.length; $('concepts').innerHTML = items.length ? items.map(x => `<div class="concept"><div><div class="concept-name">${escapeHtml(x.name)}</div><div class="concept-type">${escapeHtml(x.type || 'concept')}</div></div><span class="similarity">${Math.round((x.similarity || 0) * 100)}%</span></div>`).join('') : '<div class="empty-state">未检索到相关知识点</div>'; }
function normalizeMathText(text) { return String(text || '').replace(/```(?:latex|tex|math)\s*\n?([\s\S]*?)```/gi, (_, formula) => `\\[${formula.trim()}\\]`); }
function renderAnswer(text) { $('answer').classList.remove('empty-state'); $('answer').textContent = normalizeMathText(text || '暂无回答'); typesetMath($('answer')); }
function ensureAnswerFeedback() { if ($('answerFeedback')) return; const panel = document.createElement('div'); panel.id = 'answerFeedback'; panel.className = 'answer-feedback'; panel.innerHTML = '<span>这份回答有帮助吗？</span><button type="button" data-rating="5">有帮助</button><button type="button" data-rating="2">需改进</button><textarea aria-label="回答反馈" placeholder="可选：指出需要改进的地方"></textarea><output></output>'; $('answer').parentElement?.appendChild(panel); panel.querySelectorAll('[data-rating]').forEach(button => button.addEventListener('click', () => submitAnswerFeedback(Number(button.dataset.rating)))); }
async function submitAnswerFeedback(rating) { const panel = $('answerFeedback'); const answerId = lastAskResult?.answer_id; if (!answerId) { panel.querySelector('output').textContent = '当前回答尚未保存，暂不能提交反馈。'; return; } panel.querySelectorAll('button').forEach(button => { button.disabled = true; }); try { const response = await fetch(`${API}/ai/answers/${answerId}/feedback`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rating, feedback: panel.querySelector('textarea').value.trim() || null }) }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '提交失败'); panel.querySelector('output').textContent = '感谢反馈，已记录。'; } catch (error) { panel.querySelector('output').textContent = error.message; panel.querySelectorAll('button').forEach(button => { button.disabled = false; }); } }
function renderProof(data) { const status = data.valid ? '通过' : '需要修改'; const steps = (data.steps || []).map((s, i) => `<article class="proof-step ${s.status === 'valid' ? 'is-valid' : 'is-error'}"><div class="step-mark">${s.status === 'valid' ? '✓' : '!'}</div><div><div class="step-top"><b>步骤 ${escapeHtml(String(s.step || i + 1))}</b><span>${escapeHtml(s.error_type || 'none')}</span></div><p>${escapeHtml(s.text || '')}</p><small>${escapeHtml(s.reason || '')}</small></div></article>`).join(''); const list = (title, items) => items?.length ? `<div class="proof-notes"><b>${title}</b><ul>${items.map(x => `<li>${escapeHtml(String(x))}</li>`).join('')}</ul></div>` : ''; $('proofResult').classList.remove('empty-state'); $('proofResult').innerHTML = `<div class="proof-summary"><div><span class="section-label">REVIEW RESULT</span><h3>${status}</h3><p>${escapeHtml(data.summary || '')}</p></div><span class="review-badge ${data.valid ? 'good' : 'warn'}">${data.valid ? 'VALID' : 'REVIEW'}</span></div>${steps ? `<div class="proof-steps">${steps}</div>` : ''}${list('缺失条件', data.missing_assumptions)}${list('建议', data.suggestions)}`; typesetMath($('proofResult')); }
async function requestAskStream(question, signal) { const response = await fetch(`${API}/ai/ask-stream`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }), signal }); if (!response.ok) { const data = await response.json(); throw new Error(data.detail || '请求失败'); } const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '', result = null; $('answer').classList.remove('empty-state'); $('answer').textContent = ''; while (true) { const chunk = await reader.read(); if (chunk.done) break; buffer += decoder.decode(chunk.value, { stream: true }); const frames = buffer.split('\n\n'); buffer = frames.pop(); for (const frame of frames) { const dataLine = frame.split('\n').find(line => line.startsWith('data: ')); if (!dataLine) continue; const data = JSON.parse(dataLine.slice(6)); const eventId = frame.split('\n').find(line => line.startsWith('id: ')); if (eventId) $('answer').dataset.lastEventId = eventId.slice(4); if (frame.includes('event: progress')) $('answerStatus').textContent = data.stage; if (frame.includes('event: token')) { $('answer').textContent += data.text || ''; $('answerStatus').textContent = '正在输出'; } if (frame.includes('event: error')) throw new Error(data.detail || '生成失败'); if (frame.includes('event: result')) result = data; } } if (!result) throw new Error('未收到完整回答'); return result; }
async function requestAskStream(question, signal, requestId = crypto.randomUUID()) { let lastError; for (let attempt = 0; attempt < 2; attempt += 1) { try { const response = await fetch(`${API}/ai/ask-stream?request_id=${encodeURIComponent(requestId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }), signal }); if (!response.ok) { const data = await response.json(); throw new Error(data.detail || '请求失败'); } const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '', result = null; $('answer').classList.remove('empty-state'); if (attempt === 0) $('answer').textContent = ''; while (true) { const chunk = await reader.read(); if (chunk.done) break; buffer += decoder.decode(chunk.value, { stream: true }); const frames = buffer.split('\n\n'); buffer = frames.pop(); for (const frame of frames) { const dataLine = frame.split('\n').find(line => line.startsWith('data: ')); if (!dataLine) continue; const data = JSON.parse(dataLine.slice(6)); const eventId = frame.split('\n').find(line => line.startsWith('id: ')); if (eventId) $('answer').dataset.lastEventId = eventId.slice(4); if (frame.includes('event: progress')) $('answerStatus').textContent = data.stage; if (frame.includes('event: token')) { $('answer').textContent += data.text || ''; $('answerStatus').textContent = '正在输出'; } if (frame.includes('event: error')) throw new Error(data.detail || '生成失败'); if (frame.includes('event: result')) result = data; } } if (result) return result; throw new Error('流式连接中断'); } catch (error) { if (error.name === 'AbortError' || attempt === 1) throw error; lastError = error; $('answerStatus').textContent = '连接中断，正在恢复…'; await new Promise(resolve => setTimeout(resolve, 800)); } } throw lastError || new Error('流式连接失败'); }

async function ask(event) {
  event.preventDefault();
  const question = $('question').value.trim();
  if (!question) return;
  clearMessage();
  askController = new AbortController();
  const timeout = setTimeout(() => askController.abort(), 90000);
  $('askButton').disabled = true;
  $('askButton').innerHTML = '正在推理…';
  $('cancelAskButton').classList.remove('hidden');
  $('answerStatus').textContent = '生成中';
  try {
    const data = await requestAskStream(question, askController.signal);
    renderAnswer(data.answer);
    renderConcepts(data.concepts);
    const sourceNames = { deepseek_extended: '深入生成完成', backup_model: '备用模型生成完成', local_fallback: '本地兜底生成完成' };
    const quality = data.answer_quality;
    const qualityLabel = quality ? ` · 完整度 ${Math.round((quality.completeness_score ?? quality.score ?? 0) * 100)}% · 数学正确性未验证` : '';
    $('answerStatus').textContent = (sourceNames[data.answer_source] || (data.cache_hit ? '缓存命中' : '已完成')) + qualityLabel;
    if (data.knowledge_graph) renderGraph(data.knowledge_graph);
  } catch (error) {
    if (error.name === 'AbortError') {
      showMessage('推理已取消或超过 90 秒，当前连接已释放。');
      $('answerStatus').textContent = '已取消';
    } else {
      $('answerStatus').textContent = '连接中断，正在恢复任务…';
      const recovered = await recoverTaskResult(lastAskRequestId);
      if (recovered) {
        lastAskResult = recovered;
        renderAnswer(recovered.answer);
        renderConcepts(recovered.concepts);
        if (recovered.knowledge_graph) renderGraph(recovered.knowledge_graph);
        $('answerStatus').textContent = recovered.answer_source === 'local_fallback' ? '本地兜底生成完成' : '断线后已恢复回答';
      } else {
        showMessage(`暂时无法连接 Math Agent：${error.message}`);
        $('answerStatus').textContent = '连接失败';
      }
    }
  } finally {
    clearTimeout(timeout);
    askController = null;
    $('askButton').disabled = false;
    $('askButton').innerHTML = '开始推理 <span>→</span>';
    $('cancelAskButton').classList.add('hidden');
  }
}
async function recoverTaskResult(requestId) { if (!requestId) return null; for (let attempt = 0; attempt < 30; attempt += 1) { await new Promise(resolve => setTimeout(resolve, 1500)); try { const response = await nativeFetch(`${API}/ai/tasks/${encodeURIComponent(requestId)}`); const task = await response.json(); if (!response.ok) return null; $('answerStatus').textContent = task.stage || '恢复任务状态'; if (task.result?.answer) return task.result; if (['failed', 'cancelled'].includes(task.status)) return null; } catch (error) { return null; } } return null; }
function ensureTaskDetailPanel() { if ($('taskDetail')) return; const panel = document.createElement('details'); panel.id = 'taskDetail'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>任务详情</summary><div class="task-detail-info"><span class="muted">选择一个任务查看详情</span></div>'; $('graph').appendChild(panel); }
async function retryTask(requestId) { try { const response = await fetch(`${API}/ai/tasks/${encodeURIComponent(requestId)}/retry`, { method: 'POST' }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '重新执行失败'); showMessage(`任务已重新加入队列：${data.job_id}`); $('taskDetail').querySelector('[data-task-retry]')?.remove(); loadTaskHistory(); } catch (error) { showMessage(`重新执行失败：${error.message}`); } }
function renderTaskDetail(task) { ensureTaskDetailPanel(); const result = task.result || {}; const degradation = (result.degradation || []).join(' → ') || '无'; $('taskDetail').open = true; $('taskDetail').querySelector('.task-detail-info').innerHTML = `<div><b>${escapeHtml(task.status || '未知')}</b> · ${escapeHtml(task.stage || '')}</div><div>请求 ID：<code>${escapeHtml(task.request_id || '')}</code></div><div>更新时间：${escapeHtml(task.updated_at || '—')}</div>${result.generation_elapsed_seconds != null ? `<div>生成耗时：${result.generation_elapsed_seconds}s / 预算 ${result.generation_budget_seconds || '—'}s</div>` : ''}<div>降级链路：${escapeHtml(degradation)}</div>${task.error_detail || task.detail ? `<div class="task-error">错误：${escapeHtml(task.error_detail || task.detail)}</div>` : ''}`; }
function cancelAsk() { askController?.abort(); }
function ensureAskCancelButton() { const button = document.createElement('button'); button.type = 'button'; button.id = 'cancelAskButton'; button.className = 'cancel-ask hidden'; button.textContent = '取消推理'; button.addEventListener('click', cancelAsk); $('askButton').parentElement?.appendChild(button); }
async function pollGraphRetry(jobId) { for (let attempt = 0; attempt < 30; attempt += 1) { await new Promise(resolve => setTimeout(resolve, 2000)); try { const response = await fetch(`${API}/ai/retry-queue/${encodeURIComponent(jobId)}`); const job = await response.json(); if (!response.ok) return; if (job.status === 'succeeded' && job.result?.knowledge_graph) { activeCandidateId = job.result.candidate_id; $('graphEditor').value = JSON.stringify(job.result.knowledge_graph, null, 2); $('saveGraphButton').classList.remove('hidden'); renderGraph(job.result.knowledge_graph); loadCandidateStats(); loadCandidateHistory(); showMessage('后台重试成功，相关知识图谱已自动载入。'); return; } if (job.status === 'failed') { showMessage(`后台重试仍未成功：${job.error || '未知错误'}`); return; } $('graphStatus').textContent = `后台重试中（第 ${job.attempts || 0} 次）`; } catch (error) { return; } } showMessage('后台重试仍在进行，可稍后查看候选图谱历史。'); }
async function pollAnswerRetry(jobId) { $('answerStatus').textContent = '答案完整度不足，后台正在优化…'; for (let attempt = 0; attempt < 45; attempt += 1) { await new Promise(resolve => setTimeout(resolve, 2000)); try { const response = await fetch(`${API}/ai/retry-queue/${encodeURIComponent(jobId)}`); const job = await response.json(); if (!response.ok) return; if (job.status === 'succeeded' && job.result?.answer) { renderAnswer(job.result.answer); if (job.result.answer_quality) $('answerStatus').textContent = `后台优化完成 · 完整度 ${Math.round(((job.result.answer_quality.completeness_score ?? job.result.answer_quality.score) || 0) * 100)}% · 数学正确性未验证`; showMessage('已用后台重试结果替换原答案。'); return; } if (job.status === 'failed') { $('answerStatus').textContent = '已完成 · 后台优化失败'; return; } } catch (error) { return; } } $('answerStatus').textContent = '已完成 · 后台优化仍在进行'; }
async function enqueueGraphRetry(question) { try { const response = await fetch(`${API}/ai/retry-queue`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operation: 'related_graph', question, priority: 10 }) }); const job = await response.json(); if (response.ok) { showMessage(`本次生成失败，已加入高优先级重试队列（任务 ${job.id}）。正在等待结果…`); pollGraphRetry(job.id); } } catch (error) {} }
function collectConversationGraphContext() {
  const messages = [...document.querySelectorAll('#chatTimeline .chat-message')]
    .map((message) => {
      const role = message.classList.contains('user') ? '用户' : 'AI 助手';
      const content = message.querySelector('.chat-bubble')?.textContent?.trim() || '';
      return content ? `${role}：${content}` : '';
    })
    .filter(Boolean);
  const draft = $('question').value.trim();
  if (draft) messages.push(`用户（尚未发送）：${draft}`);
  return messages.join('\n\n');
}

async function generateRelatedGraph() {
  const context = collectConversationGraphContext();
  if (!context) {
    showMessage('请先输入一个数学问题或知识点，再生成相关图谱。');
    $('question').focus();
    return;
  }
  const draft = $('question').value.trim();
  const question = activeConversationId ? (draft || '根据本次对话生成图谱') : context;
  clearMessage();
  const button = $('generateGraphButton');
  button.disabled = true;
  button.innerHTML = '正在理解本次对话…';
  $('graphStatus').textContent = 'AI 正在根据整段对话规划知识关系';
  $('saveGraphButton').classList.add('hidden');
  $('graphCanvas').innerHTML = '<div class="empty-state">AI 正在综合本次对话中的概念、定义与推导关系，这通常需要几十秒…</div>';
  try {
    const response = await fetch(`${API}/ai/related-graph`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, conversation_id: activeConversationId || null }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '图谱请求失败');
    activeCandidateId = data.candidate_id;
    $('saveGraphButton').classList.remove('hidden');
    $('graphEditor').value = JSON.stringify(data.knowledge_graph, null, 2);
    $('graphEditorPanel').open = false;
    renderConcepts(data.concepts);
    renderGraph(data.knowledge_graph);
    document.querySelector('#graph').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    $('graphStatus').textContent = '生成失败';
    $('graphCanvas').innerHTML = '<div class="empty-state">AI 图谱暂时不可用，已转入后台重试。</div>';
    showMessage(`无法立即生成相关知识图谱：${error.message}`);
    enqueueGraphRetry(question);
  } finally {
    button.disabled = false;
    button.innerHTML = '根据本次对话生成图谱 <span>◎</span>';
  }
}
async function applyGraphEdit() { if (!activeCandidateId) return; let graph; try { graph = JSON.parse($('graphEditor').value); } catch (error) { showMessage('编辑内容不是合法 JSON，请检查后再应用。'); return; } const button = $('applyGraphEdit'); button.disabled = true; button.textContent = '保存修改中…'; try { const response = await fetch(`${API}/ai/graph-candidates/${activeCandidateId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ graph }) }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '修改失败'); renderGraph(data.knowledge_graph); $('saveGraphButton').classList.remove('hidden'); $('graphStatus').textContent = '已修改 · 待重新校验'; showMessage('图谱修改已保存，请点击“校验并保存”完成 AI 复核。'); } catch (error) { showMessage(`无法应用图谱修改：${error.message}`); } finally { button.disabled = false; button.textContent = '应用修改'; } }
async function loadCandidate(candidateId) { try { const response = await fetch(`${API}/ai/graph-candidates/${candidateId}`); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '候选图谱读取失败'); activeCandidateId = data.id; $('question').value = data.question; $('graphEditor').value = JSON.stringify(data.knowledge_graph, null, 2); $('graphEditorPanel').open = false; $('saveGraphButton').classList.toggle('hidden', data.status === 'saved'); renderGraph(data.knowledge_graph); loadCandidateEvents(candidateId); showMessage(`已载入候选图谱：${data.status}`); } catch (error) { showMessage(`无法载入候选图谱：${error.message}`); } }
async function loadCandidateEvents(candidateId) { try { const response = await fetch(`${API}/ai/graph-candidates/${candidateId}/events`); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '事件读取失败'); let timeline = $('candidateTimeline'); if (!timeline) { timeline = document.createElement('div'); timeline.id = 'candidateTimeline'; timeline.className = 'candidate-timeline'; $('graphEditorPanel').appendChild(timeline); } const names = { generated: 'AI 生成', edited: '人工编辑', validated: '校验通过', rejected: '校验拒绝', validation_failed: '校验异常', relation_conflict: '关系冲突处理', saved: '写入知识库' }; const detailText = event => event.action === 'relation_conflict' ? `${event.detail.action === 'replaced' ? '已替换' : '已跳过'}：${event.detail.old_relations?.join(', ')} → ${event.detail.new_relation}（优先级 ${event.detail.old_priority} / ${event.detail.new_priority}）` : ''; timeline.innerHTML = `<b>审核记录</b>${(data.events || []).map(event => `<div><span>${escapeHtml(names[event.action] || event.action)}${detailText(event) ? ` · ${escapeHtml(detailText(event))}` : ''}</span><small>${escapeHtml(event.created_at || '')}</small></div>`).join('') || '<span class="muted">暂无记录</span>'}`; } catch (error) {} }
async function loadCandidateHistory() { try { const status = $('candidateStatusFilter').value; const query = status ? `?status=${encodeURIComponent(status)}&limit=12` : '?limit=12'; const response = await fetch(`${API}/ai/graph-candidates${query}`); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '候选记录读取失败'); const statusNames = { pending: '待审核', needs_review: '需复核', validated: '已校验', saved: '已保存', rejected: '已拒绝' }; $('candidateList').innerHTML = data.items.length ? data.items.map(item => `<button type="button" class="candidate-item" data-candidate-id="${item.id}"><span class="candidate-question">${escapeHtml(item.question)}</span><span class="candidate-meta"><b class="candidate-status status-${escapeHtml(item.status)}">${escapeHtml(statusNames[item.status] || item.status)}</b><span>${item.node_count} 节点 · ${item.edge_count} 关系</span></span></button>`).join('') : '<span class="muted">暂无符合条件的候选图谱</span>'; document.querySelectorAll('.candidate-item').forEach(item => item.addEventListener('click', () => loadCandidate(item.dataset.candidateId))); } catch (error) { $('candidateList').innerHTML = '<span class="muted">候选记录暂不可用</span>'; } }
async function validateAndSaveGraph() {
  if (!activeCandidateId) return;
  const button = $('saveGraphButton');
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 45000);
  button.disabled = true;
  button.textContent = 'AI 校验中…';
  $('graphStatus').textContent = '正在校验数学关系（最长 45 秒）';
  try {
    const validationResponse = await fetch(`${API}/ai/graph-candidates/${activeCandidateId}/validate`, { method: 'POST', signal: controller.signal });
    const validation = await validationResponse.json();
    if (!validationResponse.ok) throw new Error(validation.detail || `校验失败（HTTP ${validationResponse.status}）`);
    if (validation.status !== 'validated') throw new Error('AI 判定存在需要复核的数学关系，暂未保存。');
    const saveResponse = await fetch(`${API}/ai/graph-candidates/${activeCandidateId}/save`, { method: 'POST', signal: controller.signal });
    const saved = await saveResponse.json();
    if (!saveResponse.ok) throw new Error(saved.detail || '保存失败');
    $('graphStatus').textContent = `已保存 · 新增 ${saved.created_concepts} 个知识点`;
    button.textContent = '已保存到知识库';
    showMessage(`图谱已通过 AI 校验并保存：新增 ${saved.created_concepts} 个知识点、${saved.created_relations} 条关系。`);
    loadCandidateHistory();
  } catch (error) {
    button.textContent = '校验并保存';
    $('graphStatus').textContent = error.name === 'AbortError' ? '校验超时 · 请稍后重试' : '待复核';
    showMessage(error.name === 'AbortError' ? 'AI 校验超过 45 秒，已自动取消；候选图谱仍保留，可稍后重试。' : `图谱暂未保存：${error.message}`);
  } finally {
    window.clearTimeout(timeout);
    button.disabled = false;
  }
}
async function analyzeProof(event) { event.preventDefault(); const question = $('proofQuestion').value.trim(), proof = $('proofDraft').value.trim(); if (!question || !proof) return; clearMessage(); $('proofButton').disabled = true; $('proofButton').innerHTML = '审查中…'; $('proofResult').classList.remove('empty-state'); $('proofResult').innerHTML = '<div class="proof-loading">正在逐步核对证明链…</div>'; try { const response = await fetch(`${API}/ai/proof-analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, proof }) }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '请求失败'); renderProof(data); } catch (error) { showMessage(`证明审查暂不可用：${error.message}`); $('proofResult').innerHTML = '<div class="empty-state">请检查后端服务或稍后重试。</div>'; } finally { $('proofButton').disabled = false; $('proofButton').innerHTML = '检查证明 <span>→</span>'; } }
function ensureConceptSearch() {
  if ($('conceptSearch')) return;
  const tools = $('graph').querySelector('.graph-tools');
  const search = document.createElement('div');
  search.className = 'concept-search';
  search.innerHTML = '<input id="conceptSearch" type="search" placeholder="查询已有知识点" aria-label="查询已有知识点"><button type="button" id="conceptSearchButton">查询网络</button><div id="conceptSearchResults" class="concept-search-results" role="listbox"></div>';
  tools?.parentElement?.insertAdjacentElement('afterend', search);
  const input = $('conceptSearch');
  const results = $('conceptSearchResults');
  const runSearch = async () => {
    const query = input.value.trim();
    results.innerHTML = '<span>查询中…</span>';
    try {
      const response = await fetch(`${API}/concepts/search?q=${encodeURIComponent(query)}&limit=12`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '查询失败');
      results.innerHTML = data.items.length ? data.items.map(item => `<button type="button" role="option" data-concept-id="${item.id}"><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.field || '数学知识')} · ${escapeHtml(item.type || 'concept')}</small></button>`).join('') : '<span>数据库中暂无匹配知识点</span>';
      results.querySelectorAll('[data-concept-id]').forEach(button => button.addEventListener('click', async () => {
        try {
          const networkResponse = await fetch(`${API}/concepts/${button.dataset.conceptId}/network`);
          const network = await networkResponse.json();
          if (!networkResponse.ok) throw new Error(network.detail || '网络读取失败');
          renderGraph(network);
          $('graphStatus').textContent = `已加载：${button.querySelector('b').textContent} · ${network.nodes.length} 个节点`;
          results.classList.remove('is-visible');
          showMessage(`已从数据库加载“${button.querySelector('b').textContent}”的已有知识网络。`);
        } catch (error) { showMessage(`知识网络加载失败：${error.message}`); }
      }));
      results.classList.add('is-visible');
    } catch (error) { results.innerHTML = '<span>知识库查询暂不可用</span>'; results.classList.add('is-visible'); }
  };
  $('conceptSearchButton').addEventListener('click', runSearch);
  input.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); runSearch(); } });
  document.addEventListener('click', event => { if (!search.contains(event.target)) results.classList.remove('is-visible'); });
}

function initKnowledgeLibrary() {
  const form = $('knowledgeSearchForm');
  if (!form) return;
  const input = $('knowledgeSearchInput');
  const filter = $('knowledgeTypeFilter');
  const results = $('knowledgeSearchResults');
  const status = $('knowledgeSearchStatus');
  const detail = $('knowledgeDetail');
  let latestItems = [];
  const renderResults = items => {
    latestItems = items;
    results.innerHTML = items.length ? items.map((item, index) => '<button type="button" class="library-result" data-library-index="' + index + '"><span><b>' + escapeHtml(item.name) + '</b><small>' + escapeHtml(item.field || '数学知识') + ' · ' + escapeHtml(item.type || 'concept') + '</small></span><i>查看 →</i></button>').join('') : '<div class="library-empty">没有找到匹配的知识点</div>';
    results.querySelectorAll('[data-library-index]').forEach(button => button.addEventListener('click', () => showDetail(latestItems[Number(button.dataset.libraryIndex)])));
  };
  const showDetail = async item => {
    if (!item) return;
    detail.classList.remove('hidden');
    detail.innerHTML = '<div class="library-detail-head"><span class="graph-card-tag">' + escapeHtml(item.type || 'concept').toUpperCase() + ' · ' + escapeHtml(item.field || '数学知识') + '</span><button type="button" aria-label="关闭知识点详情">×</button></div><h3>' + escapeHtml(item.name) + '</h3><p>' + escapeHtml(item.description || '该知识点暂无定义。') + '</p><div class="library-detail-actions"><button type="button" data-library-network>加载关系网络</button><button type="button" data-library-add>带入当前对话</button></div><div class="library-detail-network">选择操作查看更多信息</div>';
    detail.querySelector('button[aria-label]').onclick = () => detail.classList.add('hidden');
    detail.querySelector('[data-library-add]').onclick = () => {
      const question = $('question');
      const prefix = question.value.trim() ? question.value.trim() + '\\n\\n' : '';
      question.value = prefix + '请结合知识点“' + item.name + '”继续讲解。';
      question.focus();
      showMessage('已将“' + item.name + '”带入当前对话输入框。');
      document.querySelector('#ask')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
    detail.querySelector('[data-library-network]').onclick = async event => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = '加载中…';
      try {
        const response = await fetch(API + '/concepts/' + item.id + '/network');
        const network = await response.json();
        if (!response.ok) throw new Error(network.detail || '关系网络读取失败');
        renderGraph(network);
        $('graphStatus').textContent = '已加载：' + item.name + ' · ' + network.nodes.length + ' 个节点';
        detail.querySelector('.library-detail-network').textContent = '已加载 ' + network.nodes.length + ' 个节点、' + network.edges.length + ' 条关系。';
        document.querySelector('#graph')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } catch (error) {
        detail.querySelector('.library-detail-network').textContent = '关系网络暂不可用：' + error.message;
      } finally { button.disabled = false; button.textContent = '加载关系网络'; }
    };
  };
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const query = input.value.trim();
    const type = filter.value;
    status.textContent = '正在检索本地知识库…';
    results.innerHTML = '<div class="library-empty">正在检索…</div>';
    try {
      const response = await fetch(API + '/concepts/search?q=' + encodeURIComponent(query) + '&limit=50');
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '检索失败');
      const items = type ? data.items.filter(item => item.type === type) : data.items;
      renderResults(items);
      status.textContent = '找到 ' + items.length + ' 个知识点' + (query ? ' · “' + query + '”' : '');
    } catch (error) {
      status.textContent = '知识库暂不可用';
      results.innerHTML = '<div class="library-empty">' + escapeHtml(error.message) + '</div>';
    }
  });
}

async function loadGraph() { $('graphStatus').textContent = '加载中'; try { const response = await fetch(`${API}/concepts/graph`); if (!response.ok) throw Error('图谱请求失败'); renderGraph(await response.json()); } catch (error) { $('graphStatus').textContent = '暂不可用'; $('graphCanvas').innerHTML = '<div class="empty-state">请先启动后端服务</div>'; } }
function graphHash(value) { return [...String(value)].reduce((hash, char) => ((hash << 5) - hash + char.charCodeAt(0)) | 0, 0) >>> 0; }

async function loadCandidateStats() {
  const filter = $('candidateStatusFilter');
  if (!filter) return;
  let summary = $('candidateStats');
  if (!summary) {
    summary = document.createElement('div');
    summary.id = 'candidateStats';
    summary.className = 'candidate-summary';
    filter.parentElement?.insertBefore(summary, filter.parentElement.firstChild);
  }
  try {
    const response = await fetch(`${API}/ai/graph-candidates/stats`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '统计读取失败');
    const counts = data.by_status || {};
    summary.textContent = `待审核 ${counts.pending || 0} · 需复核 ${counts.needs_review || 0} · 已保存 ${counts.saved || 0} · 共 ${data.total || 0}`;
  } catch (error) {
    summary.textContent = '候选统计暂不可用';
  }
}

async function loadRetryJobs() { let panel = $('retryJobs'); if (!panel) { panel = document.createElement('details'); panel.id = 'retryJobs'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>后台重试任务</summary><div class="retry-list"></div>'; $('graph').appendChild(panel); } try { const response = await fetch(`${API}/ai/retry-queue?limit=12`); const data = await response.json(); if (!response.ok) throw new Error(); const names = { queued: '排队中', running: '执行中', retrying: '重试中', succeeded: '已成功', failed: '失败', cancelled: '已取消' }; panel.querySelector('.retry-list').innerHTML = (data.items || []).map(job => `<div class="retry-item"><span>${escapeHtml(job.question)}</span><b class="retry-status retry-${escapeHtml(job.status)}">${names[job.status] || job.status}</b><small>${job.attempts}/${job.max_attempts}</small>${job.status === 'failed' ? `<button type="button" data-retry-id="${escapeHtml(job.id)}">重新触发</button>` : ''}${['queued', 'running', 'retrying'].includes(job.status) ? `<button type="button" data-cancel-id="${escapeHtml(job.id)}">取消</button>` : ''}</div>`).join('') || '<span class="muted">暂无任务</span>'; panel.querySelectorAll('[data-retry-id]').forEach(button => button.addEventListener('click', () => retryJob(button.dataset.retryId))); panel.querySelectorAll('[data-cancel-id]').forEach(button => button.addEventListener('click', () => cancelRetryJob(button.dataset.cancelId))); } catch (error) { panel.querySelector('.retry-list').innerHTML = '<span class="muted">任务列表暂不可用</span>'; } }
async function loadCacheStatus() { let panel = $('cacheStatus'); if (!panel) { panel = document.createElement('details'); panel.id = 'cacheStatus'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>答案缓存</summary><div class="cache-info"></div>'; $('graph').appendChild(panel); } try { const response = await fetch(`${API}/ai/cache`); const data = await response.json(); if (!response.ok) throw new Error(); panel.querySelector('.cache-info').innerHTML = `<span>${data.entries} 条缓存 · 命中率 ${data.hit_rate == null ? '—' : `${Math.round(data.hit_rate * 100)}%`}</span><button type="button" id="clearAnswerCache">清空答案缓存</button>`; $('clearAnswerCache').onclick = async () => { await fetch(`${API}/ai/cache`, { method: 'DELETE' }); showMessage('答案缓存已清空。'); loadCacheStatus(); }; } catch (error) { panel.querySelector('.cache-info').textContent = '缓存状态暂不可用'; } }
async function loadHealthMetrics() { let panel = $('healthMetrics'); if (!panel) { panel = document.createElement('details'); panel.id = 'healthMetrics'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>AI 性能监控</summary><div class="health-info"></div>'; $('graph').appendChild(panel); } try { const response = await fetch(`${API}/ai/health`); const data = await response.json(); if (!response.ok) throw new Error(); const queue = Object.entries(data.retry_queue || {}).map(([status, count]) => `${status} ${count}`).join(' · ') || '无任务'; const duration = data.average_duration_seconds, firstToken = data.average_first_token_seconds; const providers = data.providers || {}; const labels = { primary: '主模型', backup: '备用模型' }; const states = { healthy: '正常', degraded: '异常', unknown: '未使用' }; const providerText = ['primary', 'backup'].map(name => { const item = providers[name] || {}; const state = states[item.state] || item.state || '未知'; const detail = item.last_error ? `：${escapeHtml(String(item.last_error).slice(0, 100))}` : ''; return `<span class="provider-status provider-${escapeHtml(item.state || 'unknown')}">${labels[name]} ${state}（成功 ${item.successes || 0} / 失败 ${item.failures || 0}）${detail}</span>`; }).join(''); const config = data.primary_model_configured ? `模型 ${escapeHtml(data.primary_model || '未知')}` : '<b class="health-warning">主模型密钥未配置</b>'; const circuitState = data.model_circuit?.state || '未知'; const circuitLabel = { open: '熔断中', half_open: '恢复探测中', closed: '正常' }[circuitState] || circuitState; const warning = duration > 20 || firstToken > 3 ? '<em class="health-warning">⚠ 检测到慢请求</em>' : ''; panel.querySelector('.health-info').innerHTML = `<div>成功率 ${data.success_rate == null ? '—' : `${Math.round(data.success_rate * 100)}%`} · 平均响应 ${duration == null ? '—' : `${duration}s`} · 首 token ${firstToken == null ? '—' : `${firstToken}s`} · 慢请求 ${data.slow_requests || 0} · 队列 ${escapeHtml(queue)}</div><div class="provider-status-list">${providerText}</div><div class="provider-config">${config} · ${escapeHtml(circuitLabel)}${warning ? ` · ${warning}` : ''}</div>`; } catch (error) { panel.querySelector('.health-info').textContent = '性能指标暂不可用'; } }
async function loadTaskHistory() { let panel = $('taskHistory'); if (!panel) { panel = document.createElement('details'); panel.id = 'taskHistory'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>最近问答任务</summary><div class="task-list"></div>'; $('graph').appendChild(panel); } try { const response = await fetch(`${API}/ai/tasks?limit=10`); const data = await response.json(); if (!response.ok) throw new Error(); const names = { queued: '准备中', retrieving: '检索中', generating: '生成中', degraded: '降级中', succeeded: '已完成', failed: '失败', cancelled: '已取消' }; panel.querySelector('.task-list').innerHTML = (data.items || []).map(item => `<div class="task-item"><span><b>${escapeHtml((item.question || '').slice(0, 48))}</b><small>${escapeHtml(names[item.status] || item.status)} · ${escapeHtml(item.stage || '')}</small></span><button type="button" data-task-id="${escapeHtml(item.request_id)}">查看</button></div>`).join('') || '<span class="muted">暂无任务记录</span>'; panel.querySelectorAll('[data-task-id]').forEach(button => button.onclick = () => restoreTask(button.dataset.taskId)); } catch (error) { panel.querySelector('.task-list').textContent = '任务历史暂不可用'; } }
async function restoreTask(requestId) { try { const response = await fetch(`${API}/ai/tasks/${encodeURIComponent(requestId)}`); const task = await response.json(); if (!response.ok) throw new Error(task.detail || '任务读取失败'); if (!task.result?.answer) { $('answerStatus').textContent = task.stage || task.status; showMessage(`任务当前状态：${task.stage || task.status}。结果将在任务完成后可恢复。`); return; } lastAskResult = task.result; renderAnswer(task.result.answer); renderConcepts(task.result.concepts); if (task.result.knowledge_graph) renderGraph(task.result.knowledge_graph); $('answerStatus').textContent = '已从任务历史恢复'; document.querySelector('#answer')?.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (error) { showMessage(`任务恢复失败：${error.message}`); } }
async function lookupRequestTrace() { const input = $('traceRequestId'); const output = $('traceResult'); const requestId = input.value.trim(); if (!requestId) { output.textContent = '请输入 request_id'; return; } output.textContent = '查询中…'; try { const response = await fetch(`${API}/ai/requests/${encodeURIComponent(requestId)}`); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '查询失败'); output.innerHTML = data.items.map(item => `<div class="trace-row"><b>${escapeHtml(item.status)}</b><span>${item.duration_seconds == null ? '—' : `${item.duration_seconds}s`}</span><span>${escapeHtml(item.error_code || 'success')}</span><small>${escapeHtml(item.created_at || '')}</small></div>`).join(''); } catch (error) { output.textContent = error.message; } }
async function loadAnswerStats() { let panel = $('answerStats'); if (!panel) { panel = document.createElement('details'); panel.id = 'answerStats'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>答案质量统计</summary><div class="health-info"></div>'; $('graph').appendChild(panel); } try { const data = await (await fetch(`${API}/ai/answers/stats`)).json(); const levels = data.quality_levels || {}; const sources = Object.entries(data.by_source || {}).map(([name, value]) => `${escapeHtml(name)} ${Math.round((value.average_quality || 0) * 100)}%/${value.count}次`).join(' · '); panel.querySelector('.health-info').innerHTML = `回答 ${data.total || 0} · 反馈 ${data.feedback_count || 0} · 平均评分 ${data.average_rating ?? '—'}<br>质量：优 ${levels.good || 0} · 部分 ${levels.partial || 0} · 弱 ${levels.weak || 0}${sources ? `<br>来源：${sources}` : ''}`; } catch (error) { panel.querySelector('.health-info').textContent = '质量统计暂不可用'; } }
async function loadAnswerHistory() { let panel = $('answerHistory'); if (!panel) { panel = document.createElement('details'); panel.id = 'answerHistory'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>答案历史</summary><div class="answer-history-controls"><select id="answerHistoryLevel"><option value="">全部质量</option><option value="good">优质</option><option value="partial">部分</option><option value="weak">低质量</option></select><input id="answerHistorySource" placeholder="模型来源"><button type="button" id="refreshAnswerHistory">刷新</button><a id="answerHistoryExport" target="_blank">导出 CSV</a></div><div class="template-list" id="answerHistoryList"></div><pre class="answer-history-detail" id="answerHistoryDetail"></pre>'; $('graph').appendChild(panel); $('refreshAnswerHistory').onclick = loadAnswerHistory; $('answerHistoryLevel').onchange = loadAnswerHistory; } try { const query = new URLSearchParams({limit:'12'}); const level = $('answerHistoryLevel').value, source = $('answerHistorySource').value.trim(); if (level) query.set('level', level); if (source) query.set('source', source); $('answerHistoryExport').href = `${API}/ai/answers/export?${query}`; const response = await fetch(`${API}/ai/answers?${query}`); const data = await response.json(); if (!response.ok) throw new Error(); $('answerHistoryList').innerHTML = (data.items || []).map(item => `<button type="button" class="template-item" data-answer-id="${item.id}"><span><b>${escapeHtml(item.question.slice(0, 42))}</b><small>${escapeHtml(item.answer_source)} · 质量 ${Math.round((item.quality_score || 0) * 100)}%</small></span><small>${escapeHtml(item.created_at)}</small></button>`).join('') || '<span class="muted">暂无历史回答</span>'; $('answerHistoryList').querySelectorAll('[data-answer-id]').forEach(button => button.onclick = () => loadAnswerDetail(button.dataset.answerId)); } catch (error) { $('answerHistoryList').textContent = '答案历史暂不可用'; } }
async function loadAnswerReviews() { let panel = $('answerReviews'); if (!panel) { panel = document.createElement('details'); panel.id = 'answerReviews'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>人工复核队列</summary><div class="template-list"></div>'; $('graph').appendChild(panel); } try { const data = await (await fetch(`${API}/ai/reviews?status=pending&limit=12`)).json(); panel.querySelector('.template-list').innerHTML = (data.items || []).map(item => `<div class="template-item"><span><b>回答 #${item.answer_id}</b><small>${escapeHtml(item.note || '待核对')}</small></span><span><button type="button" data-review-answer="${item.answer_id}" data-review-status="fixed">已修正</button><button type="button" data-review-answer="${item.answer_id}" data-review-status="false_positive">误报</button></span></div>`).join('') || '<span class="muted">暂无待复核答案</span>'; panel.querySelectorAll('[data-review-answer]').forEach(button => button.onclick = async () => { await fetch(`${API}/ai/answers/${button.dataset.reviewAnswer}/review`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status:button.dataset.reviewStatus})}); loadAnswerReviews(); }); } catch (error) { panel.querySelector('.template-list').textContent = '复核队列暂不可用'; } }
async function loadSecurityEvents() { let panel = $('securityEvents'); if (!panel) { panel = document.createElement('details'); panel.id = 'securityEvents'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>安全事件</summary><div class="answer-history-controls"><select id="securityEventFilter"><option value="">全部事件</option><option value="login_failed">登录失败</option><option value="login_rate_limited">登录限流</option><option value="admin_denied">权限拒绝</option><option value="login_succeeded">登录成功</option></select><button type="button" id="enableSecurityNotifications">开启桌面通知</button><button type="button" id="refreshSecurityEvents">刷新</button></div><div class="health-info" id="securityAlertStatus"></div><div class="template-list"></div>'; $('graph').appendChild(panel); $('refreshSecurityEvents').onclick = loadSecurityEvents; $('securityEventFilter').onchange = loadSecurityEvents; $('enableSecurityNotifications').onclick = async () => { if (window.Notification) { await Notification.requestPermission(); $('securityAlertStatus').textContent = Notification.permission === 'granted' ? '桌面通知已开启' : '未获得通知权限'; } }; } try { const event = $('securityEventFilter').value; const [data, alerts] = await Promise.all([(await fetch(`${API}/ai/security-events?limit=30`)).json(), (await fetch(`${API}/ai/security-alerts`)).json()]); $('securityAlertStatus').innerHTML = alerts.alert ? `<b class="health-warning">⚠ ${alerts.alerts.map(item => escapeHtml(item.message)).join(' · ')}</b>` : '最近 10 分钟未发现异常'; notifySecurityAlerts(alerts.alerts); const items = (data.items || []).filter(item => !event || item.event === event); panel.querySelector('.template-list').innerHTML = items.map(item => `<div class="template-item"><span><b>${escapeHtml(item.event)}</b><small>${escapeHtml(item.ip_address || 'unknown')} · ${escapeHtml(item.path || '')}</small></span><small>${escapeHtml(item.created_at)}</small></div>`).join('') || '<span class="muted">暂无安全事件</span>'; } catch (error) { panel.querySelector('.template-list').textContent = '安全事件暂不可用'; } }
async function loadMaintenanceConsole() { let panel = $('maintenanceConsole'); if (!panel) { panel = document.createElement('details'); panel.id = 'maintenanceConsole'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>数据库运维</summary><div class="answer-history-controls"><button type="button" id="runIntegrityCheck">完整性巡检</button><button type="button" id="runRepairPreview">修复预览</button><button type="button" id="createManualBackup">立即备份</button><button type="button" id="listBackups">备份列表</button></div><div class="health-info" id="maintenanceStatus">默认只读，不会修改数据。</div><pre id="maintenanceResult"></pre>'; $('graph').appendChild(panel); $('runIntegrityCheck').onclick = async () => { $('maintenanceStatus').textContent = '巡检中…'; const response = await fetch(`${API}/maintenance/integrity`); const data = await response.json(); $('maintenanceStatus').textContent = response.ok ? (data.healthy ? '数据健康' : '发现异常，请查看修复预览') : '巡检失败'; $('maintenanceResult').textContent = JSON.stringify(data, null, 2); }; $('runRepairPreview').onclick = async () => { $('maintenanceStatus').textContent = '生成修复预览…'; const response = await fetch(`${API}/maintenance/integrity/repair-preview?limit=100`); const data = await response.json(); $('maintenanceStatus').textContent = response.ok ? '预览完成：仍未修改数据' : '预览失败'; $('maintenanceResult').textContent = JSON.stringify(data, null, 2); }; $('createManualBackup').onclick = async () => { $('maintenanceStatus').textContent = '备份中…'; const response = await fetch(`${API}/maintenance/backup`, {method:'POST'}); const data = await response.json(); $('maintenanceStatus').textContent = response.ok ? `备份完成：${data.size_bytes} bytes` : (data.detail || '备份失败'); $('maintenanceResult').textContent = JSON.stringify(data, null, 2); }; $('listBackups').onclick = async () => { const response = await fetch(`${API}/maintenance/backups`); const data = await response.json(); $('maintenanceResult').textContent = JSON.stringify(data, null, 2); }; } }
async function loadAnswerDetail(answerId) { try { const response = await fetch(`${API}/ai/answers/${encodeURIComponent(answerId)}`); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '读取失败'); $('answerHistoryDetail').textContent = `${data.question}\n\n${data.answer}\n\n反馈：${(data.feedback || []).map(item => `${item.rating}星 ${item.feedback || ''}`).join('；') || '暂无'}`; typesetMath($('answerHistoryDetail')); } catch (error) { $('answerHistoryDetail').textContent = error.message; } }
function showFormulaFixes(fixes) { let panel = $('formulaFixes'); if (!fixes || !fixes.length) { if (panel) panel.remove(); return; } if (!panel) { panel = document.createElement('details'); panel.id = 'formulaFixes'; panel.className = 'formula-fixes'; $('answer').prepend(panel); } panel.innerHTML = `<summary>公式已自动修复（${fixes.length} 处）</summary><div>${fixes.map(fix => `<span>${escapeHtml(fix)}</span>`).join('')}</div>`; }
function ensureTracePanel() { const panel = document.createElement('details'); panel.id = 'tracePanel'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>请求追踪详情</summary><div class="trace-search"><input id="traceRequestId" placeholder="输入 request_id" aria-label="request_id"><button type="button" id="traceLookup">查询</button></div><div id="traceResult" class="trace-result">输入请求 ID 查询链路</div>'; $('graph').appendChild(panel); $('traceLookup').addEventListener('click', lookupRequestTrace); }
async function loadRequestLogs() { let panel = $('requestLogs'); if (!panel) { panel = document.createElement('details'); panel.id = 'requestLogs'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>最近请求日志</summary><div class="request-log-controls"><select id="requestLogStatus"><option value="">全部状态</option><option value="succeeded">成功</option><option value="failed">失败</option></select><button type="button" id="refreshRequestLogs">刷新</button><a id="exportRequestLogs" target="_blank">导出 CSV</a></div><div id="requestLogList" class="request-log-list"></div>'; $('graph').appendChild(panel); $('refreshRequestLogs').onclick = loadRequestLogs; $('requestLogStatus').onchange = loadRequestLogs; } const status = $('requestLogStatus').value; const query = new URLSearchParams({ limit: '20' }); if (status) query.set('status', status); $('exportRequestLogs').href = `${API}/ai/requests/export?${query}`; try { const response = await fetch(`${API}/ai/requests?${query}`); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '读取失败'); $('requestLogList').innerHTML = (data.items || []).map(item => `<div class="request-log-row"><span title="${escapeHtml(item.question || '')}">${escapeHtml((item.question || '无问题').slice(0, 32))}</span><b class="retry-status retry-${escapeHtml(item.status)}">${item.status === 'succeeded' ? '成功' : '失败'}</b><small>${item.duration_seconds == null ? '—' : `${item.duration_seconds}s`} · ${escapeHtml(item.created_at || '')}</small></div>`).join('') || '<span class="muted">暂无请求日志</span>'; } catch (error) { $('requestLogList').textContent = `日志暂不可用：${error.message}`; } }
async function retryJob(jobId) { try { const response = await fetch(`${API}/ai/retry-queue/${encodeURIComponent(jobId)}/retry`, { method: 'POST' }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '重新触发失败'); showMessage(`已重新触发后台任务：${data.id}`); loadRetryJobs(); } catch (error) { showMessage(`重新触发失败：${error.message}`); } }
async function loadLocalTemplates() { let panel = $('localTemplates'); if (!panel) { panel = document.createElement('details'); panel.id = 'localTemplates'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>本地回答模板</summary><form class="template-form"><input name="template_id" placeholder="模板 ID" required><input name="pattern" placeholder="匹配正则" required><textarea name="answer" placeholder="模板答案" required></textarea><button>新增模板</button></form><div class="template-list"></div>'; $('graph').appendChild(panel); panel.querySelector('form').onsubmit = async event => { event.preventDefault(); const form = event.currentTarget; const data = Object.fromEntries(new FormData(form)); const response = await fetch(`${API}/local-templates`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) }); if (!response.ok) { showMessage('模板新增失败'); return; } form.reset(); showMessage('模板已新增'); loadLocalTemplates(); }; } try { const response = await fetch(`${API}/local-templates`); const data = await response.json(); if (!response.ok) throw new Error(); panel.querySelector('.template-list').innerHTML = (data.items || []).map(item => `<div class="template-item"><div><b>${escapeHtml(item.template_id)}</b><small>${escapeHtml(item.pattern)}</small></div><label><input type="checkbox" data-template-toggle="${escapeHtml(item.template_id)}" ${item.enabled ? 'checked' : ''}>启用</label><button type="button" data-template-delete="${escapeHtml(item.template_id)}">删除</button></div>`).join('') || '<span class="muted">暂无自定义模板</span>'; panel.querySelectorAll('[data-template-toggle]').forEach(input => input.onchange = async () => { await fetch(`${API}/local-templates/${encodeURIComponent(input.dataset.templateToggle)}`, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({enabled: input.checked}) }); }); panel.querySelectorAll('[data-template-delete]').forEach(button => button.onclick = async () => { if (!confirm('确定删除此模板？')) return; await fetch(`${API}/local-templates/${encodeURIComponent(button.dataset.templateDelete)}`, {method:'DELETE'}); loadLocalTemplates(); }); } catch (error) { panel.querySelector('.template-list').textContent = '模板服务暂不可用'; } }
function ensureTemplatePreview() { const panel = document.createElement('details'); panel.id = 'templatePreview'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>模板匹配预览</summary><div class="template-preview"><input id="templatePreviewQuestion" placeholder="输入问题测试已启用模板"><button type="button" id="templatePreviewButton">测试匹配</button><output id="templatePreviewResult"></output></div>'; $('graph').appendChild(panel); $('templatePreviewButton').onclick = async () => { const question = $('templatePreviewQuestion').value.trim(); if (!question) return; const response = await fetch(`${API}/local-templates/preview`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question})}); const data = await response.json(); $('templatePreviewResult').textContent = data.matched ? `命中 ${data.template_id}：${data.answer}` : '未命中模板'; }; }
function ensureTemplateHistory() { const panel = document.createElement('details'); panel.id = 'templateHistory'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>模板历史与回滚</summary><div class="template-preview"><input id="templateHistoryId" placeholder="模板 ID"><button type="button" id="templateHistoryButton">查询历史</button></div><div id="templateHistoryList" class="template-list"></div>'; $('graph').appendChild(panel); $('templateHistoryButton').onclick = async () => { const id = $('templateHistoryId').value.trim(); if (!id) return; const response = await fetch(`${API}/local-templates/${encodeURIComponent(id)}/events`); const data = await response.json(); $('templateHistoryList').innerHTML = (data.events || []).map(event => `<div class="template-item"><span>${escapeHtml(event.action)}<small>${escapeHtml(event.detail || '')}</small></span><small>${escapeHtml(event.created_at)}</small>${event.action === 'updated' || event.action === 'deleted' ? `<button type="button" data-rollback-event="${event.id}">回滚</button>` : ''}</div>`).join('') || '<span class="muted">暂无历史事件</span>'; $('templateHistoryList').querySelectorAll('[data-rollback-event]').forEach(button => button.onclick = async () => { await fetch(`${API}/local-templates/${encodeURIComponent(id)}/rollback/${button.dataset.rollbackEvent}`, {method:'POST'}); showMessage('模板已回滚'); loadLocalTemplates(); }); }; }
async function loadTemplateStats() { let panel = $('templateStats'); if (!panel) { panel = document.createElement('details'); panel.id = 'templateStats'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>模板审核统计</summary><div class="health-info"></div>'; $('graph').appendChild(panel); } try { const data = await (await fetch(`${API}/local-templates/stats`)).json(); const counts = data.by_status || {}; panel.querySelector('.health-info').textContent = `总计 ${data.total || 0} · 启用 ${data.enabled || 0} · 待审核 ${counts.pending || 0} · 已通过 ${counts.approved || 0} · 已驳回 ${counts.rejected || 0}`; } catch (error) { panel.querySelector('.health-info').textContent = '统计暂不可用'; } }
async function loadTemplateUsage() { let panel = $('templateUsage'); if (!panel) { panel = document.createElement('details'); panel.id = 'templateUsage'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>模板命中率</summary><div class="health-info"></div>'; $('graph').appendChild(panel); } try { const data = await (await fetch(`${API}/local-templates/usage`)).json(); const top = (data.items || []).filter(item => item.hit_count).slice(0, 3).map(item => `${escapeHtml(item.template_id)} ${item.hit_count}次`).join(' · '); panel.querySelector('.health-info').innerHTML = `总命中 ${data.total_hits || 0}${top ? ` · 热门：${top}` : ''}`; } catch (error) { panel.querySelector('.health-info').textContent = '命中统计暂不可用'; } }
async function loadTemplateRecommendations() { let panel = $('templateRecommendations'); if (!panel) { panel = document.createElement('details'); panel.id = 'templateRecommendations'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>模板优化建议</summary><div class="health-info"></div>'; $('graph').appendChild(panel); } try { const data = await (await fetch(`${API}/local-templates/recommendations`)).json(); panel.querySelector('.health-info').textContent = data.total ? data.items.map(item => `${item.template_id}：${item.reason}`).join(' · ') : '暂无优化建议'; } catch (error) { panel.querySelector('.health-info').textContent = '建议暂不可用'; } }
async function loadSampleStats() { let panel = $('sampleStats'); if (!panel) { panel = document.createElement('details'); panel.id = 'sampleStats'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>匿名问题样本</summary><div class="health-info"></div>'; $('graph').appendChild(panel); } try { const data = await (await fetch(`${API}/local-templates/samples/stats`)).json(); panel.querySelector('.health-info').textContent = `样本 ${data.total || 0} · 已命中模板 ${data.matched || 0}`; } catch (error) { panel.querySelector('.health-info').textContent = '样本统计暂不可用'; } }
async function loadSampleRecommendations() { let panel = $('sampleRecommendations'); if (!panel) { panel = document.createElement('details'); panel.id = 'sampleRecommendations'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>样本补充建议</summary><div class="health-info"></div>'; $('graph').appendChild(panel); } try { const data = await (await fetch(`${API}/local-templates/samples/recommendations`)).json(); panel.querySelector('.health-info').textContent = `${data.recommendation} 未命中 ${data.unmatched} 条`; } catch (error) { panel.querySelector('.health-info').textContent = '样本建议暂不可用'; } }
async function loadTemplateAuditLog() { let panel = $('templateAuditLog'); if (!panel) { panel = document.createElement('details'); panel.id = 'templateAuditLog'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>模板操作审计</summary><div class="template-list"></div>'; $('graph').appendChild(panel); } try { const data = await (await fetch(`${API}/local-templates/audit-log`)).json(); panel.querySelector('.template-list').innerHTML = (data.items || []).map(item => `<div class="template-item"><span>${escapeHtml(item.action)}<small>${escapeHtml(item.detail || '')}</small></span><small>${escapeHtml(item.created_at)}</small></div>`).join('') || '<span class="muted">暂无操作记录</span>'; } catch (error) { panel.querySelector('.template-list').textContent = '审计日志暂不可用'; } }
function ensureAuditExport() { const panel = document.createElement('details'); panel.id = 'auditExport'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>审计日志导出</summary><div class="template-preview"><select id="auditAction"><option value="">全部操作</option><option value="export">导出</option><option value="import">导入</option><option value="template_reviewed">审核</option><option value="sample_cleanup">样本清理</option></select><a id="auditExportLink" target="_blank">下载 CSV</a></div>'; $('graph').appendChild(panel); $('auditAction').onchange = () => $('auditExportLink').href = `${API}/local-templates/audit-log/export${$('auditAction').value ? `?action=${encodeURIComponent($('auditAction').value)}` : ''}`; $('auditAction').onchange(); }
async function ensureTemplateAB() { const panel = document.createElement('details'); panel.id = 'templateAB'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>模板 A/B 测试</summary><div class="template-preview"><select id="templateABOne"></select><select id="templateABTwo"></select><textarea id="templateABQuestions" placeholder="每行一个问题样本"></textarea><button type="button" id="templateABRun">开始测试</button><output id="templateABResult"></output></div>'; $('graph').appendChild(panel); try { const data = await (await fetch(`${API}/local-templates?enabled=true`)).json(); const items = (data.items || []).filter(item => item.review_status === 'approved'); const options = items.map(item => `<option value="${escapeHtml(item.template_id)}">${escapeHtml(item.template_id)}</option>`).join(''); $('templateABOne').innerHTML = options; $('templateABTwo').innerHTML = options; } catch (error) { $('templateABResult').textContent = '模板读取失败'; } $('templateABRun').onclick = async () => { const questions = $('templateABQuestions').value.split(/\r?\n/).map(x => x.trim()).filter(Boolean); const ids = [$('templateABOne').value, $('templateABTwo').value]; if (ids[0] === ids[1] || !questions.length) { $('templateABResult').textContent = '请选择两个不同模板并输入问题样本'; return; } const response = await fetch(`${API}/local-templates/ab-test`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({template_ids:ids, questions})}); const data = await response.json(); $('templateABResult').textContent = response.ok ? `${data.results.map(item => `${item.template_id}：${Math.round(item.hit_rate * 100)}%`).join(' · ')} · 胜出：${data.winner}` : (data.detail || '测试失败'); }; }
function ensureTemplateBackup() { const panel = document.createElement('details'); panel.id = 'templateBackup'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>模板备份与迁移</summary><div class="template-preview"><button type="button" id="templateExport">导出 JSON</button><input id="templateImportJson" placeholder="粘贴导出的 JSON"><button type="button" id="templateImport">导入</button><output id="templateBackupResult"></output></div>'; $('graph').appendChild(panel); $('templateExport').onclick = async () => { const response = await fetch(`${API}/local-templates/export`); const blob = new Blob([JSON.stringify(await response.json(), null, 2)], {type:'application/json'}); const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'math-agent-templates.json'; link.click(); URL.revokeObjectURL(link.href); }; $('templateImport').onclick = async () => { try { const data = JSON.parse($('templateImportJson').value); const response = await fetch(`${API}/local-templates/import`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}); const result = await response.json(); if (!response.ok) throw new Error(result.detail || '导入失败'); $('templateBackupResult').textContent = `已导入 ${result.total} 条`; loadLocalTemplates(); } catch (error) { $('templateBackupResult').textContent = error.message; } }; }
async function loadTemplateReview() { let panel = $('templateReview'); if (!panel) { panel = document.createElement('details'); panel.id = 'templateReview'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>模板审核</summary><div class="template-preview"><select id="templateReviewStatus"><option value="pending">待审核</option><option value="approved">已通过</option><option value="rejected">已驳回</option></select><button type="button" id="templateReviewRefresh">刷新</button></div><div id="templateReviewList" class="template-list"></div>'; $('graph').appendChild(panel); $('templateReviewRefresh').onclick = loadTemplateReview; $('templateReviewStatus').onchange = loadTemplateReview; } const status = $('templateReviewStatus').value; try { const data = await (await fetch(`${API}/local-templates?enabled=true`)).json(); const items = (data.items || []).filter(item => item.review_status === status); $('templateReviewList').innerHTML = items.map(item => `<div class="template-item"><span><b>${escapeHtml(item.template_id)}</b><small>${escapeHtml(item.pattern)}</small></span><span class="template-review-status">${status === 'pending' ? '待审核' : status === 'approved' ? '已通过' : '已驳回'}</span><span>${['approved','rejected','pending'].map(next => `<button type="button" data-review="${next}" data-template-id="${escapeHtml(item.template_id)}">${next === 'approved' ? '通过' : next === 'rejected' ? '驳回' : '重置'}</button>`).join('')}</span></div>`).join('') || '<span class="muted">暂无模板</span>'; $('templateReviewList').querySelectorAll('[data-review]').forEach(button => button.onclick = async () => { await fetch(`${API}/local-templates/${encodeURIComponent(button.dataset.templateId)}/review?status=${button.dataset.review}`, {method:'POST'}); loadTemplateReview(); loadLocalTemplates(); }); } catch (error) { $('templateReviewList').textContent = '审核服务暂不可用'; } }
async function cancelRetryJob(jobId) { try { const response = await fetch(`${API}/ai/retry-queue/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '取消失败'); showMessage('后台重试任务已取消。'); loadRetryJobs(); } catch (error) { showMessage(`取消失败：${error.message}`); } }

function ensureBatchAuditButton() {
  if ($('batchValidateCandidates')) return;
  const filter = $('candidateStatusFilter');
  if (!filter) return;
  const button = document.createElement('button');
  button.type = 'button';
  button.id = 'batchValidateCandidates';
  button.className = 'batch-audit-button';
  button.textContent = '批量校验当前列表';
  button.addEventListener('click', batchValidateCandidates);
  filter.parentElement?.appendChild(button);
  const saveButton = button.cloneNode(false);
  saveButton.id = 'batchSaveCandidates';
  saveButton.textContent = '预览并保存已校验';
  saveButton.addEventListener('click', batchSaveCandidates);
  filter.parentElement?.appendChild(saveButton);
}

async function batchValidateCandidates() {
  const ids = [...document.querySelectorAll('.candidate-item')].map(item => Number(item.dataset.candidateId)).filter(Number.isInteger);
  if (!ids.length) { showMessage('当前没有可批量校验的候选图谱。'); return; }
  const button = $('batchValidateCandidates');
  button.disabled = true;
  button.textContent = '批量校验中…';
  try {
    const response = await fetch(`${API}/ai/graph-candidates/batch-validate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ candidate_ids: ids }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '批量校验失败');
    const summary = Object.entries(data.summary || {}).map(([status, count]) => `${status}: ${count}`).join(' · ');
    showMessage(`批量校验完成：${summary || '无结果'}`);
    await loadCandidateStats();
    await loadCandidateHistory();
  } catch (error) {
    showMessage(`批量校验失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = '批量校验当前列表';
  }
}

async function batchSaveCandidates() {
  const ids = [...document.querySelectorAll('.candidate-item')].map(item => Number(item.dataset.candidateId)).filter(Number.isInteger);
  if (!ids.length) { showMessage('当前没有候选图谱可保存。'); return; }
  const button = $('batchSaveCandidates');
  button.disabled = true;
  button.textContent = '读取保存预览…';
  try {
    const previewResponse = await fetch(`${API}/ai/graph-candidates/batch-save-preview`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ candidate_ids: ids }) });
    const preview = await previewResponse.json();
    if (!previewResponse.ok) throw new Error(preview.detail || '预览失败');
    const validated = (preview.items || []).filter(item => item.status === 'validated');
    if (!validated.length) throw new Error('当前列表没有已通过校验的候选图谱。');
    const confirmed = window.confirm(`将保存 ${validated.length} 张图谱，新增约 ${preview.summary?.new_concepts || 0} 个知识点。是否继续？`);
    if (!confirmed) return;
    button.textContent = '批量保存中…';
    const response = await fetch(`${API}/ai/graph-candidates/batch-save`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ candidate_ids: validated.map(item => item.candidate_id) }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '批量保存失败');
    showMessage(`批量保存完成：新增 ${data.summary.created_concepts} 个知识点、${data.summary.created_relations} 条关系。`);
    await loadCandidateStats();
    await loadCandidateHistory();
  } catch (error) {
    showMessage(`批量保存未完成：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = '预览并保存已校验';
  }
}

function renderGraph(graph) {
  const nodes = (graph.nodes || []).slice(0, 28), edges = (graph.edges || graph.relations || []).map(edge => ({ ...edge, source: typeof edge.source === 'object' ? edge.source.id : edge.source, target: typeof edge.target === 'object' ? edge.target.id : edge.target })).slice(0, 45);
  activeGraphContext = { nodes, edges };
  if (!nodes.length) { $('graphCanvas').innerHTML = '<div class="empty-state">知识图谱暂无数据</div>'; return; }
  const width = 1000, height = 420, center = { x: width / 2, y: height / 2 }, positions = {};
  nodes.forEach((node, index) => { const ring = index < 5 ? 0 : index < 14 ? 1 : 2, count = ring === 0 ? Math.min(nodes.length, 5) : ring === 1 ? Math.min(Math.max(nodes.length - 5, 0), 9) : Math.max(nodes.length - 14, 1), offset = ring === 0 ? index : ring === 1 ? index - 5 : index - 14, angle = (Math.PI * 2 * offset / count) - Math.PI / 2 + (ring ? .18 : 0), radius = [90, 160, 245][ring], jitter = (graphHash(node.id) % 18) - 9; positions[node.id] = { x: center.x + Math.cos(angle) * (radius + jitter), y: center.y + Math.sin(angle) * (radius + jitter), ring }; });
  const particles = Array.from({ length: 46 }, (_, index) => { const seed = graphHash(`particle-${index}`), x = 18 + (seed % 965), y = 14 + ((seed >>> 9) % 390), size = 1 + ((seed >>> 17) % 3); return `<circle class="ambient-particle" cx="${x}" cy="${y}" r="${size / 2}" style="animation-delay:-${(seed % 6000) / 1000}s"/>`; }).join('');
  const edgeMarkup = edges.filter(edge => positions[edge.source] && positions[edge.target]).map((edge, index) => { const a = positions[edge.source], b = positions[edge.target], color = typeColor[nodes.find(n => n.id === edge.source)?.type] || '#55d8ff', path = `M ${a.x.toFixed(1)} ${a.y.toFixed(1)} L ${b.x.toFixed(1)} ${b.y.toFixed(1)}`; return `<g class="graph-edge"><path d="${path}"/><path class="edge-glow" d="${path}"/><circle class="edge-pulse" r="2.2" fill="${color}"><animateMotion dur="${3.8 + (index % 4) * .7}s" repeatCount="indefinite" path="${path}"/></circle></g>`; }).join('');
  const nodeMarkup = nodes.map((node, index) => { const p = positions[node.id], color = typeColor[node.type] || typeColor.concept, radius = p.ring === 0 ? 16 : p.ring === 1 ? 13 : 10, labelY = p.y + radius + 19; return `<g class="graph-node graph-node-${escapeHtml(node.type || 'concept')}" role="button" tabindex="0" aria-label="查看 ${escapeHtml(node.name)} 在聊天中的出处" data-graph-node-id="${escapeHtml(String(node.id))}" style="--node-color:${color};animation-delay:${index * 65}ms"><circle class="node-orbit" cx="${p.x}" cy="${p.y}" r="${radius + 10}"/><circle class="node-halo" cx="${p.x}" cy="${p.y}" r="${radius + 5}"/><circle class="node-core" cx="${p.x}" cy="${p.y}" r="${radius}"/><circle class="node-specular" cx="${p.x - radius * .28}" cy="${p.y - radius * .32}" r="${Math.max(2, radius * .22)}"/><text x="${p.x}" y="${labelY}" text-anchor="middle">${escapeHtml(node.name).slice(0, 14)}</text><title>${escapeHtml(node.name)} · ${escapeHtml(node.type || 'concept')} · 点击回看聊天出处</title></g>`; }).join('');
  $('graphCanvas').innerHTML = `<div class="graph-vignette"></div><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="数学知识图谱，包含 ${nodes.length} 个知识点和 ${edges.length} 条关系"><defs><radialGradient id="graph-depth" cx="50%" cy="44%"><stop offset="0" stop-color="#163b59"/><stop offset=".5" stop-color="#0b1e32"/><stop offset="1" stop-color="#07111f"/></radialGradient></defs><rect width="100%" height="100%" fill="url(#graph-depth)"/>${particles}<g class="graph-rings"><circle cx="${center.x}" cy="${center.y}" r="90"/><circle cx="${center.x}" cy="${center.y}" r="160"/><circle cx="${center.x}" cy="${center.y}" r="245"/></g><g class="graph-edges">${edgeMarkup}</g><g class="graph-nodes">${nodeMarkup}</g></svg>`;
  $('graphCanvas').querySelectorAll('[data-graph-node-id]').forEach(element => {
    const node = nodes.find(item => String(item.id) === element.dataset.graphNodeId);
    const showNode = () => { openGraphConceptCard(node); highlightConversationMessages(node?.name); };
    element.addEventListener('click', showNode);
    element.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); showNode(); } });
  });
  $('graphStatus').textContent = `${nodes.length} 个节点 · ${edges.length} 条关系`;
  $('legend').innerHTML = '<span class="legend-concept">概念</span><span class="legend-theorem">定理</span><span class="legend-property">性质</span><span class="legend-method">方法</span><em>点击节点回看聊天出处</em>';
}

function highlightConversationMessages(conceptName) {
  const needle = String(conceptName || '').trim().toLocaleLowerCase();
  const messages = [...document.querySelectorAll('#chatTimeline .chat-message')];
  messages.forEach(message => message.classList.remove('is-source-message'));
  if (!needle) return;
  const matches = messages.filter(message => (message.querySelector('.chat-bubble')?.textContent || '').toLocaleLowerCase().includes(needle));
  matches.forEach(message => message.classList.add('is-source-message'));
  matches[0]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function conversationMatches(conceptName) {
  const needle = String(conceptName || '').trim().toLocaleLowerCase();
  if (!needle) return [];
  return [...document.querySelectorAll('#chatTimeline .chat-message')].filter(message => (message.querySelector('.chat-bubble')?.textContent || '').toLocaleLowerCase().includes(needle));
}

async function loadRetryAlerts() { let panel = $('retryAlerts'); if (!panel) { panel = document.createElement('details'); panel.id = 'retryAlerts'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>重试失败告警</summary><div class="retry-alert-info"></div>'; $('graph').appendChild(panel); } try { const response = await fetch(`${API}/ai/retry-alerts?window_minutes=60`); const data = await response.json(); if (!response.ok) throw new Error(); panel.querySelector('.retry-alert-info').innerHTML = data.alert ? `<b class="health-warning">⚠ 最近 1 小时有 ${data.failed_count} 个任务最终失败</b>${(data.items || []).slice(0, 3).map(item => `<div class="retry-alert-item"><span>${escapeHtml(item.question)}</span><small>${escapeHtml(item.error || '未知错误')}</small></div>`).join('')}` : '<span class="muted">最近 1 小时没有最终失败任务</span>'; } catch (error) { panel.querySelector('.retry-alert-info').textContent = '重试告警暂不可用'; } }
async function loadOperationsDashboard() { let panel = $('operationsDashboard'); if (!panel) { panel = document.createElement('details'); panel.id = 'operationsDashboard'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>运营健康总览</summary><div class="ops-dashboard-info"></div>'; $('graph').appendChild(panel); } try { const response = await fetch(`${API}/ai/ops-dashboard?window_minutes=60`); const data = await response.json(); if (!response.ok) throw new Error(); const sources = Object.entries(data.by_source || {}).map(([name, value]) => `${escapeHtml(name)} ${Math.round((value.average_quality || 0) * 100)}%/${value.count}次`).join(' · ') || '暂无回答'; const providers = Object.entries(data.provider_failure_rates || {}).map(([name, value]) => `${escapeHtml(name)} ${value.failure_rate == null ? '—' : `${Math.round(value.failure_rate * 100)}%`}`).join(' · '); panel.querySelector('.ops-dashboard-info').innerHTML = `<b class="ops-${escapeHtml(data.health || 'healthy')}">${data.health === 'degraded' ? '需要关注' : '运行正常'}</b><div>回答 ${data.answer_count || 0} · 平均质量 ${data.average_quality == null ? '—' : `${Math.round(data.average_quality * 100)}%`} · 平均耗时 ${data.average_duration_seconds == null ? '—' : `${data.average_duration_seconds}s`} · 失败重试 ${data.failed_retry_jobs || 0}</div><div>来源：${sources}</div><div>供应商失败率：${providers || '暂无调用'}</div>`; } catch (error) { panel.querySelector('.ops-dashboard-info').textContent = '运营统计暂不可用'; } }
async function openGraphConceptCard(concept) {
  const card = $('graphConceptCard');
  if (!card || !concept) return;
  const sourceMessages = conversationMatches(concept.name);
  const relatedEdges = activeGraphContext.edges.filter(edge => String(edge.source) === String(concept.id) || String(edge.target) === String(concept.id)).slice(0, 8);
  const relationMarkup = relatedEdges.length
    ? relatedEdges.map(edge => {
      const otherId = String(edge.source) === String(concept.id) ? edge.target : edge.source;
      const other = activeGraphContext.nodes.find(node => String(node.id) === String(otherId));
      const relation = edge.relation || edge.type || 'related';
      const relationSources = conversationMatches(`${concept.name} ${other?.name || ''}`).length;
      return `<span class="graph-source-relation"><b>${escapeHtml(relation)}</b> → ${escapeHtml(other?.name || String(otherId))}<small>${relationSources ? `${relationSources} 条消息共同提及` : '来自当前图谱推断'}</small></span>`;
    }).join('')
    : '<span>暂无当前图谱关系</span>';
  card.classList.remove('hidden');
  card.innerHTML = `<div class="graph-card-head"><div><span class="graph-card-tag">${escapeHtml(concept.type || 'concept').toUpperCase()} · ${escapeHtml(concept.field || '数学知识')}</span><h4>${escapeHtml(concept.name)}</h4></div><button class="graph-card-close" type="button" aria-label="关闭概念卡片">×</button></div><p>${escapeHtml(concept.description || '该知识点暂无说明。')}</p><div class="graph-card-sources"><b>对话出处</b><span>${sourceMessages.length ? `当前对话中出现 ${sourceMessages.length} 条消息` : '当前对话未直接提及，由图谱关系推断'}</span></div><div class="graph-card-relations"><b>关系来源</b><div>${relationMarkup}</div></div><div class="graph-card-path"><b>推荐学习顺序</b><span>正在生成路径…</span></div><div class="graph-card-links"><span>正在读取关联知识点…</span></div>`;
  card.querySelector('.graph-card-close').onclick = () => card.classList.add('hidden');
  try {
    const [response, pathResponse, progressResponse] = await Promise.all([
      fetch(`${API}/concepts/${encodeURIComponent(concept.id)}/relations`),
      fetch(`${API}/concepts/${encodeURIComponent(concept.id)}/learning-path`),
      fetch(`${API}/concepts/learning-progress`),
    ]);
    const [data, path, progress] = await Promise.all([response.json(), pathResponse.json(), progressResponse.json()]);
    if (!response.ok) throw new Error(data.detail || '关联读取失败');
    const links = [...(data.prerequisites || []), ...(data.next_concepts || []), ...(data.related || [])].slice(0, 8);
    card.querySelector('.graph-card-links').innerHTML = links.length
      ? links.map(item => `<span>${escapeHtml(item.name)} · ${escapeHtml(item.relation || 'related')}</span>`).join('')
      : '<span>暂无已保存的直接关联</span>';
    const pathElement = card.querySelector('.graph-card-path');
    const completedIds = new Set(progress.completed_concept_ids || []);
    pathElement.innerHTML = pathResponse.ok
      ? `<b>推荐学习顺序</b><div>${(path.steps || []).map((item, index) => `<button type="button" class="learning-step${completedIds.has(item.id) ? ' is-complete' : ''}" data-learning-concept="${item.id}">${completedIds.has(item.id) ? '✓ ' : ''}${index + 1}. ${escapeHtml(item.name)}</button>`).join('<i>→</i>')}${path.cycle_detected ? '<small>已忽略循环前置关系</small>' : ''}</div>`
      : '<b>推荐学习顺序</b><span>暂时无法生成路径</span>';
    pathElement.querySelectorAll('[data-learning-concept]').forEach(button => button.addEventListener('click', async () => {
      const conceptId = Number(button.dataset.learningConcept);
      const done = button.classList.contains('is-complete');
      button.disabled = true;
      try {
        const saveResponse = await fetch(`${API}/concepts/${conceptId}/learning-progress`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: done ? 'learning' : 'completed' }) });
        if (!saveResponse.ok) throw new Error('保存失败');
        await openGraphConceptCard(concept);
        loadLearningPulse();
      } catch (error) {
        showMessage('学习进度保存失败，请稍后重试。');
        button.disabled = false;
      }
    }));
  } catch (error) {
    card.querySelector('.graph-card-links').textContent = '关联知识点暂不可用';
  }
}

async function loadLearningPulse() {
  const panel = $('learningPulse');
  if (!panel) return;
  try {
    const response = await fetch(`${API}/concepts/learning-progress`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '读取失败');
    const summary = data.summary || {};
    panel.querySelector('.learning-pulse-track i').style.width = `${summary.percent || 0}%`;
    panel.querySelector('strong').textContent = summary.total ? `已掌握 ${summary.completed || 0} / ${summary.total} · ${summary.percent || 0}%` : '知识库尚未加入可学习的知识点';
    const next = panel.querySelector('.learning-pulse-next');
    const concepts = summary.next_concepts || [];
    next.innerHTML = concepts.length ? concepts.map(item => `<button type="button" data-pulse-concept="${item.id}">下一步：${escapeHtml(item.name)}</button>`).join('') : '<span class="muted">已完成当前知识库</span>';
    next.querySelectorAll('[data-pulse-concept]').forEach(button => button.addEventListener('click', async () => {
      const response = await fetch(`${API}/concepts/${encodeURIComponent(button.dataset.pulseConcept)}`);
      const concept = await response.json();
      if (!response.ok || !concept.id) { showMessage('知识点暂不可用。'); return; }
      $('graph').scrollIntoView({ behavior: 'smooth', block: 'start' });
      openGraphConceptCard(concept);
    }));
  } catch (error) {
    panel.querySelector('strong').textContent = '学习进度暂不可用';
  }
}

$('askForm').addEventListener('submit', ask);
ensureAskCancelButton();
ensureAnswerFeedback();
ensureAdminPanel();
initKnowledgeLibrary();
$('generateGraphButton').addEventListener('click', generateRelatedGraph);
$('saveGraphButton').addEventListener('click', validateAndSaveGraph);
$('applyGraphEdit').addEventListener('click', applyGraphEdit);
$('graphHistory').addEventListener('toggle', () => { if ($('graphHistory').open) { loadCandidateStats(); loadCandidateHistory(); } });
$('candidateStatusFilter').addEventListener('change', loadCandidateHistory);
$('proofForm').addEventListener('submit', analyzeProof);
$('refreshGraph').addEventListener('click', loadGraph);
ensureBatchAuditButton();
loadGraph();
loadLearningPulse();
loadCandidateStats();
loadCandidateHistory();
const loadRetryAlertsBase = loadRetryAlerts;
loadRetryAlerts = async function () {
  await loadRetryAlertsBase();
  try {
    const data = await (await fetch(`${API}/ai/retry-alerts?window_minutes=60`)).json();
    const panel = $('retryAlerts');
    const rates = Object.entries(data.provider_failure_rates || {}).map(([name, value]) => `${name} 失败率 ${value.failure_rate == null ? '—' : `${Math.round(value.failure_rate * 100)}%`}`).join(' · ');
    const trend = (data.trend_by_hour || []).slice(-4).map(item => `${escapeHtml(item.hour.slice(11, 16))} ${item.failed_count}`).join(' · ');
    if (panel && (rates || trend)) panel.querySelector('.retry-alert-info').insertAdjacentHTML('beforeend', `<small class="retry-analytics">供应商：${escapeHtml(rates || '暂无调用')} ${trend ? ` · 每小时失败：${trend}` : ''}</small>`);
  } catch (error) { /* 基础告警已渲染 */ }
};
let operationsWindowMinutes = 60;
const loadOperationsDashboardBase = loadOperationsDashboard;
loadOperationsDashboard = async function () {
  await loadOperationsDashboardBase();
  const panel = $('operationsDashboard');
  if (!panel) return;
  let controls = panel.querySelector('.ops-controls');
  if (!controls) { controls = document.createElement('div'); controls.className = 'ops-controls'; controls.innerHTML = '<label>时间范围 <select><option value="60">1 小时</option><option value="360">6 小时</option><option value="1440">24 小时</option><option value="10080">7 天</option></select></label><a target="_blank">导出 CSV</a>'; panel.querySelector('summary').after(controls); controls.querySelector('select').value = String(operationsWindowMinutes); controls.querySelector('select').onchange = () => { operationsWindowMinutes = Number(controls.querySelector('select').value); loadOperationsDashboard(); }; }
  controls.querySelector('a').href = `${API}/ai/ops-dashboard/export?window_minutes=${operationsWindowMinutes}`;
  try { const response = await fetch(`${API}/ai/ops-dashboard?window_minutes=${operationsWindowMinutes}`); const data = await response.json(); if (!response.ok) throw new Error(); const sources = Object.entries(data.by_source || {}).map(([name, value]) => `${escapeHtml(name)} ${Math.round((value.average_quality || 0) * 100)}%/${value.count}次`).join(' · ') || '暂无回答'; const providers = Object.entries(data.provider_failure_rates || {}).map(([name, value]) => `${escapeHtml(name)} ${value.failure_rate == null ? '—' : `${Math.round(value.failure_rate * 100)}%`}`).join(' · '); panel.querySelector('.ops-dashboard-info').innerHTML = `<b class="ops-${escapeHtml(data.health || 'healthy')}">${data.health === 'degraded' ? '需要关注' : '运行正常'}</b><div>回答 ${data.answer_count || 0} · 平均质量 ${data.average_quality == null ? '—' : `${Math.round(data.average_quality * 100)}%`} · 平均耗时 ${data.average_duration_seconds == null ? '—' : `${data.average_duration_seconds}s`} · 失败重试 ${data.failed_retry_jobs || 0}</div><div>来源：${sources}</div><div>供应商失败率：${providers || '暂无调用'}</div>`; } catch (error) { /* 基础面板已处理错误 */ }
};
loadRetryJobs();
loadRetryAlerts();
loadOperationsDashboard();
loadCacheStatus();
loadHealthMetrics();
loadTaskHistory();
loadAnswerStats();
loadAnswerHistory();
loadAnswerReviews();
loadSecurityEvents();
loadMaintenanceConsole();
ensureTracePanel();
loadRequestLogs();
loadLocalTemplates();
ensureTemplatePreview();
ensureTemplateHistory();
ensureTemplateBackup();
loadTemplateReview();
loadTemplateStats();
loadTemplateUsage();
loadTemplateRecommendations();
loadSampleStats();
loadSampleRecommendations();
loadTemplateAuditLog();
ensureAuditExport();
ensureTemplateAB();
setInterval(loadHealthMetrics, 30000);
setInterval(loadTaskHistory, 15000);
setInterval(loadRetryAlerts, 30000);
setInterval(loadOperationsDashboard, 30000);
const restoreTaskBase = restoreTask;
restoreTask = async function (requestId) {
  try {
    const response = await fetch(`${API}/ai/tasks/${encodeURIComponent(requestId)}`);
    const task = await response.json();
    if (response.ok) renderTaskDetail(task);
  } catch (error) { /* 原恢复逻辑会显示可用的错误 */ }
  return restoreTaskBase(requestId);
};
ensureTaskDetailPanel();
const renderTaskDetailBase = renderTaskDetail;
renderTaskDetail = function (task) {
  renderTaskDetailBase(task);
  const detail = $('taskDetail').querySelector('.task-detail-info');
  detail.querySelector('[data-task-retry]')?.remove();
  if (['failed', 'cancelled'].includes(task.status)) {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.taskRetry = task.request_id;
    button.className = 'task-retry-button';
    button.textContent = '重新执行';
    button.onclick = () => retryTask(task.request_id);
    detail.appendChild(button);
  }
};

function ensureUtilityDrawer() {
  if ($('utilityDrawer')) return;
  const graph = $('graph');
  const drawer = document.createElement('details');
  drawer.id = 'utilityDrawer';
  drawer.className = 'utility-drawer';
  drawer.innerHTML = '<summary><span><b>更多工具</b><small>运维、历史、模板与审核功能</small></span><em>按需展开</em></summary><div class="utility-grid"></div>';
  const grid = drawer.querySelector('.utility-grid');
  [...graph.children].filter(element => element.matches('details.retry-jobs, details.graph-history, details.graph-editor')).forEach(element => grid.appendChild(element));
  graph.appendChild(drawer);
}
ensureUtilityDrawer();
ensureConceptSearch();

// 统一将本次问答的追踪 ID 放入查询面板，便于故障后立即定位。
const originalAsk = ask;
const originalRequestAskStream = requestAskStream;
requestAskStream = async function (...args) {
  const result = await originalRequestAskStream(...args);
  lastAskResult = result;
  if (result?.request_id) $('answer').dataset.requestId = result.request_id;
  showFormulaFixes(result?.formula_fixes);
  return result;
};
ask = async function (event) {
  await originalAsk(event);
  if (lastAskResult?.quality_retry_job?.id) pollAnswerRetry(lastAskResult.quality_retry_job.id);
  const answer = $('answer');
  const requestId = answer.dataset.requestId;
  if (requestId && $('traceRequestId')) { $('traceRequestId').value = requestId; $('tracePanel').open = true; lookupRequestTrace(); }
};
$('askForm').removeEventListener('submit', originalAsk);
$('askForm').addEventListener('submit', ask);

// Conversation workspace: the legacy /ai/ask flow remains available, while the
// primary UI writes each turn to a durable context-aware conversation.
let activeConversationId = Number(localStorage.getItem('math-agent-conversation-id')) || null;

function conversationTime(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
}

function appendChatMessage(message, pending = false) {
  const timeline = $('chatTimeline');
  if (!timeline) return null;
  timeline.querySelector('.chat-welcome')?.remove();
  const item = document.createElement('article');
  item.className = `chat-message ${message.role === 'user' ? 'user' : 'assistant'}${pending ? ' pending' : ''}`;
  item.dataset.messageId = message.id || '';
  const label = document.createElement('span');
  label.className = 'chat-message-label';
  label.textContent = message.role === 'user' ? 'YOU' : 'MATH AGENT';
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';
  bubble.textContent = normalizeMathText(message.content || '');
  item.append(label, bubble);
  if (message.created_at) {
    const meta = document.createElement('small');
    meta.className = 'chat-message-meta';
    meta.textContent = conversationTime(message.created_at);
    item.appendChild(meta);
  }
  timeline.appendChild(item);
  timeline.scrollTop = timeline.scrollHeight;
  if (!pending && message.role !== 'user') typesetMath(bubble);
  return item;
}

function renderConversation(data) {
  $('chatTimeline').replaceChildren();
  $('conversationTitle').textContent = data.conversation.title || '新的数学对话';
  const messages = data.messages || [];
  if (!messages.length) {
    $('chatTimeline').innerHTML = '<div class="chat-welcome"><span>∫</span><div><b>从一个数学问题开始。</b><p>我会记住本次对话中的定义、条件与推导步骤；你可以继续追问“第二步为什么成立”。</p></div></div>';
    return;
  }
  messages.forEach(message => appendChatMessage(message));
}

async function loadConversationList() {
  const list = $('conversationList');
  try {
    const response = await fetch(`${API}/conversations`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '读取失败');
    list.innerHTML = (data.items || []).map(item => `<button type="button" class="conversation-item ${item.id === activeConversationId ? 'is-active' : ''}" data-conversation-id="${item.id}"><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.topic || `${item.message_count || 0} 条消息`)} · ${conversationTime(item.updated_at)}</small></button>`).join('') || '<span>还没有保存的对话</span>';
    list.querySelectorAll('[data-conversation-id]').forEach(button => button.addEventListener('click', () => selectConversation(Number(button.dataset.conversationId))));
  } catch (error) {
    list.innerHTML = '<span>对话服务暂不可用</span>';
  }
}

async function selectConversation(conversationId) {
  try {
    const response = await fetch(`${API}/conversations/${conversationId}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '读取失败');
    activeConversationId = conversationId;
    localStorage.setItem('math-agent-conversation-id', String(conversationId));
    renderConversation(data);
    await loadConversationList();
  } catch (error) { showMessage(`无法打开对话：${error.message}`); }
}

async function createConversation() {
  try {
    const response = await fetch(`${API}/conversations`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
    const item = await response.json();
    if (!response.ok) throw new Error(item.detail || '创建失败');
    activeConversationId = item.id;
    localStorage.setItem('math-agent-conversation-id', String(item.id));
    renderConversation({ conversation: item, messages: [] });
    await loadConversationList();
    $('question').focus();
  } catch (error) { showMessage(`无法新建对话：${error.message}`); }
}

async function ensureConversation() {
  if (activeConversationId) {
    try { await selectConversation(activeConversationId); return; } catch (error) { activeConversationId = null; }
  }
  await createConversation();
}

async function renameActiveConversation() {
  if (!activeConversationId) return;
  const title = window.prompt('为这段数学对话命名', $('conversationTitle').textContent);
  if (!title?.trim()) return;
  try {
    const response = await fetch(`${API}/conversations/${activeConversationId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: title.trim() }) });
    const item = await response.json();
    if (!response.ok) throw new Error(item.detail || '重命名失败');
    $('conversationTitle').textContent = item.title;
    loadConversationList();
  } catch (error) { showMessage(error.message); }
}

async function deleteActiveConversation() {
  if (!activeConversationId || !window.confirm('删除这段对话及其消息？此操作不能撤销。')) return;
  try {
    const response = await fetch(`${API}/conversations/${activeConversationId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('删除失败');
    activeConversationId = null;
    localStorage.removeItem('math-agent-conversation-id');
    await createConversation();
  } catch (error) { showMessage(error.message); }
}

async function requestConversationStream(question, signal) {
  const response = await fetch(`${API}/conversations/${activeConversationId}/messages/stream`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: question }), signal });
  if (!response.ok) { const data = await response.json(); throw new Error(data.detail || '请求失败'); }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let assistantItem = null;
  let result = null;
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true });
    const frames = buffer.split('\n\n');
    buffer = frames.pop();
    for (const frame of frames) {
      const event = frame.match(/event: (.+)/)?.[1];
      const raw = frame.split('\n').find(line => line.startsWith('data: '));
      if (!raw) continue;
      const data = JSON.parse(raw.slice(6));
      if (event === 'user') appendChatMessage(data);
      if (event === 'token') {
        if (!assistantItem) assistantItem = appendChatMessage({ role: 'assistant', content: '' }, true);
        const bubble = assistantItem.querySelector('.chat-bubble');
        bubble.textContent += data.text || '';
        $('chatTimeline').scrollTop = $('chatTimeline').scrollHeight;
        $('answerStatus').textContent = '正在输出';
      }
      if (event === 'result') {
        result = data.result;
        if (assistantItem) assistantItem.remove();
        appendChatMessage(data.assistant_message);
      }
      if (event === 'error') throw new Error(data.detail || '生成失败');
    }
  }
  if (!result) throw new Error('未收到完整回答');
  return result;
}

async function conversationAsk(event) {
  event.preventDefault();
  const question = $('question').value.trim();
  if (!question || !activeConversationId) return;
  clearMessage();
  askController = new AbortController();
  $('askButton').disabled = true;
  $('askButton').innerHTML = '推理中 <span>···</span>';
  $('cancelAskButton').classList.remove('hidden');
  $('answerStatus').textContent = '结合上下文推理中';
  $('chatContextStatus').textContent = '正在保存并构建上下文…';
  try {
    const data = await requestConversationStream(question, askController.signal);
    lastAskResult = data;
    renderAnswer(data.answer);
    renderConcepts(data.concepts || []);
    if (data.knowledge_graph) renderGraph(data.knowledge_graph);
    const completeness = data.answer_quality?.completeness_score ?? data.answer_quality?.score;
    $('answerStatus').textContent = (data.answer_source === 'local_fallback' ? '本地数学推导完成' : '本轮推理完成') + (completeness == null ? '' : ` · 完整度 ${Math.round(completeness * 100)}% · 数学正确性未验证`);
    $('chatContextStatus').textContent = '本轮内容已保存到对话上下文';
    $('question').value = '';
    loadConversationList();
  } catch (error) {
    $('chatContextStatus').textContent = '本轮未完成保存';
    if (error.name === 'AbortError') { $('answerStatus').textContent = '已停止生成'; showMessage('推理已停止。'); }
    else { $('answerStatus').textContent = '生成失败'; showMessage(`暂时无法完成本轮对话：${error.message}`); }
  } finally {
    askController = null;
    $('askButton').disabled = false;
    $('askButton').innerHTML = '发送 <span>↑</span>';
    $('cancelAskButton').classList.add('hidden');
  }
}

$('askForm').removeEventListener('submit', ask);
$('askForm').addEventListener('submit', conversationAsk);
$('newConversation').addEventListener('click', createConversation);
$('renameConversation').addEventListener('click', renameActiveConversation);
$('deleteConversation').addEventListener('click', deleteActiveConversation);
ensureConversation();
