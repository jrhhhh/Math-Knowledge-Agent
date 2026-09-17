const API = window.MATH_AGENT_API || 'http://127.0.0.1:8000';
const $ = (id) => document.getElementById(id);
let activeCandidateId = null;
let askController = null;
let lastAiErrorCode = null;
const typeColor = { concept: '#55d8ff', theorem: '#ffcb68', property: '#bc8cff', method: '#77f2ad' };

function showMessage(text) { const hints = { timeout: '模型响应超时，请稍后重新提交。', rate_limit: '请求较频繁，请等待片刻后重试。', network: '请检查网络或后端服务是否在线。', server_error: '模型服务暂时异常，后台会继续重试。', invalid_response: '模型返回格式异常，请重新生成。' }; const inferred = text.includes('超时') ? 'timeout' : text.includes('频繁') || text.includes('限流') ? 'rate_limit' : text.includes('连接') || text.includes('网络') ? 'network' : text.includes('格式') ? 'invalid_response' : lastAiErrorCode; const hint = Object.prototype.hasOwnProperty.call(hints, inferred) ? ` ${hints[inferred]}` : ''; $('message').textContent = `${text}${hint}`; $('message').classList.remove('hidden'); }
function clearMessage() { $('message').classList.add('hidden'); }
function typesetMath(element) { if (window.MathJax?.typesetPromise) window.MathJax.typesetPromise([element]).catch(() => {}); }
function escapeHtml(s = '') { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function renderConcepts(items = []) { $('conceptCount').textContent = items.length; $('concepts').innerHTML = items.length ? items.map(x => `<div class="concept"><div><div class="concept-name">${escapeHtml(x.name)}</div><div class="concept-type">${escapeHtml(x.type || 'concept')}</div></div><span class="similarity">${Math.round((x.similarity || 0) * 100)}%</span></div>`).join('') : '<div class="empty-state">未检索到相关知识点</div>'; }
function renderAnswer(text) { $('answer').classList.remove('empty-state'); $('answer').textContent = text || '暂无回答'; typesetMath($('answer')); }
function renderProof(data) { const status = data.valid ? '通过' : '需要修改'; const steps = (data.steps || []).map((s, i) => `<article class="proof-step ${s.status === 'valid' ? 'is-valid' : 'is-error'}"><div class="step-mark">${s.status === 'valid' ? '✓' : '!'}</div><div><div class="step-top"><b>步骤 ${escapeHtml(String(s.step || i + 1))}</b><span>${escapeHtml(s.error_type || 'none')}</span></div><p>${escapeHtml(s.text || '')}</p><small>${escapeHtml(s.reason || '')}</small></div></article>`).join(''); const list = (title, items) => items?.length ? `<div class="proof-notes"><b>${title}</b><ul>${items.map(x => `<li>${escapeHtml(String(x))}</li>`).join('')}</ul></div>` : ''; $('proofResult').classList.remove('empty-state'); $('proofResult').innerHTML = `<div class="proof-summary"><div><span class="section-label">REVIEW RESULT</span><h3>${status}</h3><p>${escapeHtml(data.summary || '')}</p></div><span class="review-badge ${data.valid ? 'good' : 'warn'}">${data.valid ? 'VALID' : 'REVIEW'}</span></div>${steps ? `<div class="proof-steps">${steps}</div>` : ''}${list('缺失条件', data.missing_assumptions)}${list('建议', data.suggestions)}`; typesetMath($('proofResult')); }
async function requestAskStream(question, signal) { const response = await fetch(`${API}/ai/ask-stream`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }), signal }); if (!response.ok) { const data = await response.json(); throw new Error(data.detail || '请求失败'); } const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '', result = null; $('answer').classList.remove('empty-state'); $('answer').textContent = ''; while (true) { const chunk = await reader.read(); if (chunk.done) break; buffer += decoder.decode(chunk.value, { stream: true }); const frames = buffer.split('\n\n'); buffer = frames.pop(); for (const frame of frames) { const dataLine = frame.split('\n').find(line => line.startsWith('data: ')); if (!dataLine) continue; const data = JSON.parse(dataLine.slice(6)); const eventId = frame.split('\n').find(line => line.startsWith('id: ')); if (eventId) $('answer').dataset.lastEventId = eventId.slice(4); if (frame.includes('event: progress')) $('answerStatus').textContent = data.stage; if (frame.includes('event: token')) { $('answer').textContent += data.text || ''; $('answerStatus').textContent = '正在输出'; } if (frame.includes('event: error')) throw new Error(data.detail || '生成失败'); if (frame.includes('event: result')) result = data; } } if (!result) throw new Error('未收到完整回答'); return result; }
async function requestAskStream(question, signal, requestId = crypto.randomUUID()) { let lastError; for (let attempt = 0; attempt < 2; attempt += 1) { try { const response = await fetch(`${API}/ai/ask-stream?request_id=${encodeURIComponent(requestId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }), signal }); if (!response.ok) { const data = await response.json(); throw new Error(data.detail || '请求失败'); } const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '', result = null; $('answer').classList.remove('empty-state'); if (attempt === 0) $('answer').textContent = ''; while (true) { const chunk = await reader.read(); if (chunk.done) break; buffer += decoder.decode(chunk.value, { stream: true }); const frames = buffer.split('\n\n'); buffer = frames.pop(); for (const frame of frames) { const dataLine = frame.split('\n').find(line => line.startsWith('data: ')); if (!dataLine) continue; const data = JSON.parse(dataLine.slice(6)); const eventId = frame.split('\n').find(line => line.startsWith('id: ')); if (eventId) $('answer').dataset.lastEventId = eventId.slice(4); if (frame.includes('event: progress')) $('answerStatus').textContent = data.stage; if (frame.includes('event: token')) { $('answer').textContent += data.text || ''; $('answerStatus').textContent = '正在输出'; } if (frame.includes('event: error')) throw new Error(data.detail || '生成失败'); if (frame.includes('event: result')) result = data; } } if (result) return result; throw new Error('流式连接中断'); } catch (error) { if (error.name === 'AbortError' || attempt === 1) throw error; lastError = error; $('answerStatus').textContent = '连接中断，正在恢复…'; await new Promise(resolve => setTimeout(resolve, 800)); } } throw lastError || new Error('流式连接失败'); }

async function ask(event) { event.preventDefault(); const question = $('question').value.trim(); if (!question) return; clearMessage(); askController = new AbortController(); const timeout = setTimeout(() => askController.abort(), 90000); $('askButton').disabled = true; $('askButton').innerHTML = '正在推理…'; $('cancelAskButton').classList.remove('hidden'); $('answerStatus').textContent = '生成中'; try { const data = await requestAskStream(question, askController.signal); renderAnswer(data.answer); renderConcepts(data.concepts); $('answerStatus').textContent = data.answer_source === 'deepseek_extended' ? '深入生成完成' : (data.cache_hit ? '缓存命中' : '已完成'); if (data.knowledge_graph) renderGraph(data.knowledge_graph); } catch (error) { if (error.name === 'AbortError') { showMessage('推理已取消或超过 90 秒，当前连接已释放。'); $('answerStatus').textContent = '已取消'; } else { showMessage(`暂时无法连接 Math Agent：${error.message}`); $('answerStatus').textContent = '连接失败'; } } finally { clearTimeout(timeout); askController = null; $('askButton').disabled = false; $('askButton').innerHTML = '开始推理 <span>→</span>'; $('cancelAskButton').classList.add('hidden'); } }
function cancelAsk() { askController?.abort(); }
function ensureAskCancelButton() { const button = document.createElement('button'); button.type = 'button'; button.id = 'cancelAskButton'; button.className = 'cancel-ask hidden'; button.textContent = '取消推理'; button.addEventListener('click', cancelAsk); $('askButton').parentElement?.appendChild(button); }
async function pollGraphRetry(jobId) { for (let attempt = 0; attempt < 30; attempt += 1) { await new Promise(resolve => setTimeout(resolve, 2000)); try { const response = await fetch(`${API}/ai/retry-queue/${encodeURIComponent(jobId)}`); const job = await response.json(); if (!response.ok) return; if (job.status === 'succeeded' && job.result?.knowledge_graph) { activeCandidateId = job.result.candidate_id; $('graphEditor').value = JSON.stringify(job.result.knowledge_graph, null, 2); $('saveGraphButton').classList.remove('hidden'); renderGraph(job.result.knowledge_graph); loadCandidateStats(); loadCandidateHistory(); showMessage('后台重试成功，相关知识图谱已自动载入。'); return; } if (job.status === 'failed') { showMessage(`后台重试仍未成功：${job.error || '未知错误'}`); return; } $('graphStatus').textContent = `后台重试中（第 ${job.attempts || 0} 次）`; } catch (error) { return; } } showMessage('后台重试仍在进行，可稍后查看候选图谱历史。'); }
async function enqueueGraphRetry(question) { try { const response = await fetch(`${API}/ai/retry-queue`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operation: 'related_graph', question, priority: 10 }) }); const job = await response.json(); if (response.ok) { showMessage(`本次生成失败，已加入高优先级重试队列（任务 ${job.id}）。正在等待结果…`); pollGraphRetry(job.id); } } catch (error) {} }
async function generateRelatedGraph() { const question = $('question').value.trim(); if (!question) { showMessage('请先输入一个数学问题或知识点，再生成相关图谱。'); $('question').focus(); return; } clearMessage(); const button = $('generateGraphButton'); button.disabled = true; button.innerHTML = 'AI 构建中…'; $('graphStatus').textContent = 'AI 正在规划知识关系'; $('saveGraphButton').classList.add('hidden'); $('graphCanvas').innerHTML = '<div class="empty-state">AI 正在提取概念、定理与推导关系，这通常需要几十秒…</div>'; try { const response = await fetch(`${API}/ai/related-graph`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '图谱请求失败'); activeCandidateId = data.candidate_id; $('saveGraphButton').classList.remove('hidden'); $('graphEditor').value = JSON.stringify(data.knowledge_graph, null, 2); $('graphEditorPanel').open = false; renderConcepts(data.concepts); renderGraph(data.knowledge_graph); document.querySelector('#graph').scrollIntoView({ behavior: 'smooth', block: 'start' }); } catch (error) { $('graphStatus').textContent = '生成失败'; $('graphCanvas').innerHTML = '<div class="empty-state">AI 图谱暂时不可用，已转入后台重试。</div>'; showMessage(`无法立即生成相关知识图谱：${error.message}`); enqueueGraphRetry(question); } finally { button.disabled = false; button.innerHTML = '生成相关图谱 <span>◎</span>'; } }
async function applyGraphEdit() { if (!activeCandidateId) return; let graph; try { graph = JSON.parse($('graphEditor').value); } catch (error) { showMessage('编辑内容不是合法 JSON，请检查后再应用。'); return; } const button = $('applyGraphEdit'); button.disabled = true; button.textContent = '保存修改中…'; try { const response = await fetch(`${API}/ai/graph-candidates/${activeCandidateId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ graph }) }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '修改失败'); renderGraph(data.knowledge_graph); $('saveGraphButton').classList.remove('hidden'); $('graphStatus').textContent = '已修改 · 待重新校验'; showMessage('图谱修改已保存，请点击“校验并保存”完成 AI 复核。'); } catch (error) { showMessage(`无法应用图谱修改：${error.message}`); } finally { button.disabled = false; button.textContent = '应用修改'; } }
async function loadCandidate(candidateId) { try { const response = await fetch(`${API}/ai/graph-candidates/${candidateId}`); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '候选图谱读取失败'); activeCandidateId = data.id; $('question').value = data.question; $('graphEditor').value = JSON.stringify(data.knowledge_graph, null, 2); $('graphEditorPanel').open = false; $('saveGraphButton').classList.toggle('hidden', data.status === 'saved'); renderGraph(data.knowledge_graph); loadCandidateEvents(candidateId); showMessage(`已载入候选图谱：${data.status}`); } catch (error) { showMessage(`无法载入候选图谱：${error.message}`); } }
async function loadCandidateEvents(candidateId) { try { const response = await fetch(`${API}/ai/graph-candidates/${candidateId}/events`); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '事件读取失败'); let timeline = $('candidateTimeline'); if (!timeline) { timeline = document.createElement('div'); timeline.id = 'candidateTimeline'; timeline.className = 'candidate-timeline'; $('graphEditorPanel').appendChild(timeline); } const names = { generated: 'AI 生成', edited: '人工编辑', validated: '校验通过', rejected: '校验拒绝', validation_failed: '校验异常', relation_conflict: '关系冲突处理', saved: '写入知识库' }; const detailText = event => event.action === 'relation_conflict' ? `${event.detail.action === 'replaced' ? '已替换' : '已跳过'}：${event.detail.old_relations?.join(', ')} → ${event.detail.new_relation}（优先级 ${event.detail.old_priority} / ${event.detail.new_priority}）` : ''; timeline.innerHTML = `<b>审核记录</b>${(data.events || []).map(event => `<div><span>${escapeHtml(names[event.action] || event.action)}${detailText(event) ? ` · ${escapeHtml(detailText(event))}` : ''}</span><small>${escapeHtml(event.created_at || '')}</small></div>`).join('') || '<span class="muted">暂无记录</span>'}`; } catch (error) {} }
async function loadCandidateHistory() { try { const status = $('candidateStatusFilter').value; const query = status ? `?status=${encodeURIComponent(status)}&limit=12` : '?limit=12'; const response = await fetch(`${API}/ai/graph-candidates${query}`); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '候选记录读取失败'); const statusNames = { pending: '待审核', needs_review: '需复核', validated: '已校验', saved: '已保存', rejected: '已拒绝' }; $('candidateList').innerHTML = data.items.length ? data.items.map(item => `<button type="button" class="candidate-item" data-candidate-id="${item.id}"><span class="candidate-question">${escapeHtml(item.question)}</span><span class="candidate-meta"><b class="candidate-status status-${escapeHtml(item.status)}">${escapeHtml(statusNames[item.status] || item.status)}</b><span>${item.node_count} 节点 · ${item.edge_count} 关系</span></span></button>`).join('') : '<span class="muted">暂无符合条件的候选图谱</span>'; document.querySelectorAll('.candidate-item').forEach(item => item.addEventListener('click', () => loadCandidate(item.dataset.candidateId))); } catch (error) { $('candidateList').innerHTML = '<span class="muted">候选记录暂不可用</span>'; } }
async function validateAndSaveGraph() { if (!activeCandidateId) return; const button = $('saveGraphButton'); button.disabled = true; button.textContent = 'AI 校验中…'; $('graphStatus').textContent = '正在校验数学关系'; try { const validationResponse = await fetch(`${API}/ai/graph-candidates/${activeCandidateId}/validate`, { method: 'POST' }); const validation = await validationResponse.json(); if (!validationResponse.ok) throw new Error(validation.detail || '校验失败'); if (validation.status !== 'validated') throw new Error('AI 判定存在需要复核的数学关系，暂未保存。'); const saveResponse = await fetch(`${API}/ai/graph-candidates/${activeCandidateId}/save`, { method: 'POST' }); const saved = await saveResponse.json(); if (!saveResponse.ok) throw new Error(saved.detail || '保存失败'); $('graphStatus').textContent = `已保存 · 新增 ${saved.created_concepts} 个知识点`; button.textContent = '已保存到知识库'; showMessage(`图谱已通过 AI 校验并保存：新增 ${saved.created_concepts} 个知识点、${saved.created_relations} 条关系。`); } catch (error) { button.textContent = '校验并保存'; $('graphStatus').textContent = '待复核'; showMessage(`图谱暂未保存：${error.message}`); } finally { button.disabled = false; } }
async function analyzeProof(event) { event.preventDefault(); const question = $('proofQuestion').value.trim(), proof = $('proofDraft').value.trim(); if (!question || !proof) return; clearMessage(); $('proofButton').disabled = true; $('proofButton').innerHTML = '审查中…'; $('proofResult').classList.remove('empty-state'); $('proofResult').innerHTML = '<div class="proof-loading">正在逐步核对证明链…</div>'; try { const response = await fetch(`${API}/ai/proof-analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, proof }) }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '请求失败'); renderProof(data); } catch (error) { showMessage(`证明审查暂不可用：${error.message}`); $('proofResult').innerHTML = '<div class="empty-state">请检查后端服务或稍后重试。</div>'; } finally { $('proofButton').disabled = false; $('proofButton').innerHTML = '检查证明 <span>→</span>'; } }
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
async function loadHealthMetrics() { let panel = $('healthMetrics'); if (!panel) { panel = document.createElement('details'); panel.id = 'healthMetrics'; panel.className = 'retry-jobs'; panel.innerHTML = '<summary>AI 性能监控</summary><div class="health-info"></div>'; $('graph').appendChild(panel); } try { const response = await fetch(`${API}/ai/health`); const data = await response.json(); if (!response.ok) throw new Error(); const queue = Object.entries(data.retry_queue || {}).map(([status, count]) => `${status} ${count}`).join(' · ') || '无任务'; const duration = data.average_duration_seconds, firstToken = data.average_first_token_seconds; const warning = duration > 20 || firstToken > 3 ? '<em class="health-warning">⚠ 检测到慢请求</em>' : ''; panel.querySelector('.health-info').innerHTML = `<span>成功率 ${data.success_rate == null ? '—' : `${Math.round(data.success_rate * 100)}%`} · 平均响应 ${duration == null ? '—' : `${duration}s`} · 首 token ${firstToken == null ? '—' : `${firstToken}s`} · 慢请求 ${data.slow_requests || 0} · 队列 ${escapeHtml(queue)}</span>${warning}`; } catch (error) { panel.querySelector('.health-info').textContent = '性能指标暂不可用'; } }
async function retryJob(jobId) { try { const response = await fetch(`${API}/ai/retry-queue/${encodeURIComponent(jobId)}/retry`, { method: 'POST' }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || '重新触发失败'); showMessage(`已重新触发后台任务：${data.id}`); loadRetryJobs(); } catch (error) { showMessage(`重新触发失败：${error.message}`); } }
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
  if (!nodes.length) { $('graphCanvas').innerHTML = '<div class="empty-state">知识图谱暂无数据</div>'; return; }
  const width = 1000, height = 420, center = { x: width / 2, y: height / 2 }, positions = {};
  nodes.forEach((node, index) => { const ring = index < 5 ? 0 : index < 14 ? 1 : 2, count = ring === 0 ? Math.min(nodes.length, 5) : ring === 1 ? Math.min(Math.max(nodes.length - 5, 0), 9) : Math.max(nodes.length - 14, 1), offset = ring === 0 ? index : ring === 1 ? index - 5 : index - 14, angle = (Math.PI * 2 * offset / count) - Math.PI / 2 + (ring ? .18 : 0), radius = [90, 160, 245][ring], jitter = (graphHash(node.id) % 18) - 9; positions[node.id] = { x: center.x + Math.cos(angle) * (radius + jitter), y: center.y + Math.sin(angle) * (radius + jitter), ring }; });
  const particles = Array.from({ length: 46 }, (_, index) => { const seed = graphHash(`particle-${index}`), x = 18 + (seed % 965), y = 14 + ((seed >>> 9) % 390), size = 1 + ((seed >>> 17) % 3); return `<circle class="ambient-particle" cx="${x}" cy="${y}" r="${size / 2}" style="animation-delay:-${(seed % 6000) / 1000}s"/>`; }).join('');
  const edgeMarkup = edges.filter(edge => positions[edge.source] && positions[edge.target]).map((edge, index) => { const a = positions[edge.source], b = positions[edge.target], color = typeColor[nodes.find(n => n.id === edge.source)?.type] || '#55d8ff', path = `M ${a.x.toFixed(1)} ${a.y.toFixed(1)} L ${b.x.toFixed(1)} ${b.y.toFixed(1)}`; return `<g class="graph-edge"><path d="${path}"/><path class="edge-glow" d="${path}"/><circle class="edge-pulse" r="2.2" fill="${color}"><animateMotion dur="${3.8 + (index % 4) * .7}s" repeatCount="indefinite" path="${path}"/></circle></g>`; }).join('');
  const nodeMarkup = nodes.map((node, index) => { const p = positions[node.id], color = typeColor[node.type] || typeColor.concept, radius = p.ring === 0 ? 16 : p.ring === 1 ? 13 : 10, labelY = p.y + radius + 19; return `<g class="graph-node graph-node-${escapeHtml(node.type || 'concept')}" style="--node-color:${color};animation-delay:${index * 65}ms"><circle class="node-orbit" cx="${p.x}" cy="${p.y}" r="${radius + 10}"/><circle class="node-halo" cx="${p.x}" cy="${p.y}" r="${radius + 5}"/><circle class="node-core" cx="${p.x}" cy="${p.y}" r="${radius}"/><circle class="node-specular" cx="${p.x - radius * .28}" cy="${p.y - radius * .32}" r="${Math.max(2, radius * .22)}"/><text x="${p.x}" y="${labelY}" text-anchor="middle">${escapeHtml(node.name).slice(0, 14)}</text><title>${escapeHtml(node.name)} · ${escapeHtml(node.type || 'concept')}</title></g>`; }).join('');
  $('graphCanvas').innerHTML = `<div class="graph-vignette"></div><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="数学知识图谱，包含 ${nodes.length} 个知识点和 ${edges.length} 条关系"><defs><radialGradient id="graph-depth" cx="50%" cy="44%"><stop offset="0" stop-color="#163b59"/><stop offset=".5" stop-color="#0b1e32"/><stop offset="1" stop-color="#07111f"/></radialGradient></defs><rect width="100%" height="100%" fill="url(#graph-depth)"/>${particles}<g class="graph-rings"><circle cx="${center.x}" cy="${center.y}" r="90"/><circle cx="${center.x}" cy="${center.y}" r="160"/><circle cx="${center.x}" cy="${center.y}" r="245"/></g><g class="graph-edges">${edgeMarkup}</g><g class="graph-nodes">${nodeMarkup}</g></svg>`;
  $('graphStatus').textContent = `${nodes.length} 个节点 · ${edges.length} 条关系`;
  $('legend').innerHTML = '<span class="legend-concept">概念</span><span class="legend-theorem">定理</span><span class="legend-property">性质</span><span class="legend-method">方法</span><em>悬停节点查看详情</em>';
}

$('askForm').addEventListener('submit', ask);
ensureAskCancelButton();
$('generateGraphButton').addEventListener('click', generateRelatedGraph);
$('saveGraphButton').addEventListener('click', validateAndSaveGraph);
$('applyGraphEdit').addEventListener('click', applyGraphEdit);
$('graphHistory').addEventListener('toggle', () => { if ($('graphHistory').open) { loadCandidateStats(); loadCandidateHistory(); } });
$('candidateStatusFilter').addEventListener('change', loadCandidateHistory);
$('proofForm').addEventListener('submit', analyzeProof);
$('refreshGraph').addEventListener('click', loadGraph);
ensureBatchAuditButton();
loadGraph();
loadCandidateStats();
loadCandidateHistory();
loadRetryJobs();
loadCacheStatus();
loadHealthMetrics();
setInterval(loadHealthMetrics, 30000);
