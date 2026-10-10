(() => {
  let items=[],editing=null;
  async function request(path,method='GET',body) {
    const response=await fetch(`${API}/notes${path}`,{method,headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})}); const data=await response.json();
    if(!response.ok) throw new Error(data.detail || '笔记操作失败');return data;
  }
  function editor(item=null) {
    editing=item; $('noteTitle').value=item?.title || ''; $('noteCourseEdit').value=item?.course || $('noteCourse').value || '未分课程'; $('noteContent').value=item?.content || ''; $('noteStatus').textContent='';
    $('noteDialogTitle').textContent=item?'编辑笔记':'新建笔记';$('noteDialog').showModal();
  }
  function render() {
    const q=$('noteSearch').value.trim().toLowerCase(),course=$('noteCourse').value,filter=$('noteFilter').value;
    const visible=items.filter(x=>(!course || x.course===course) && (!q || (x.title+' '+x.content).toLowerCase().includes(q)) && (filter==='archived'?x.archived:!x.archived && (filter!=='favorite' || x.favorite)));
    $('noteList').innerHTML=visible.length?visible.map(x=>`<article class="note-card" data-note="${x.id}"><div class="note-card-heading"><h3>${escapeHtml(x.title)}</h3><span>${escapeHtml(x.course)}</span></div><p class="note-excerpt">${escapeHtml(x.content.slice(0,180))}${x.content.length>180?'…':''}</p><div class="note-actions"><button type="button" data-note-edit>编辑</button><button type="button" data-note-favorite>${x.favorite?'取消收藏':'收藏'}</button><button type="button" data-note-archive>${x.archived?'恢复归档':'归档'}</button><a href="${API}/notes/${x.id}/export" download>导出 Markdown ↗</a></div><details><summary>阅读笔记与原始依据</summary><div class="note-full">${escapeHtml(x.content)}</div><div class="note-provenance"><b>${x.answer_id?`原回答 #${x.answer_id}`:'个人手工笔记'}</b><p>笔记可经编辑；以下原始依据不随编辑改写。模型回答或引用不等于完整数学证明。</p>${x.origin?.answer?`<details><summary>保存时的原回答</summary><div class="note-full">${escapeHtml(x.origin.answer)}</div></details>`:''}${(x.origin?.evidence || []).filter(e=>e.type!=='structural_quality' && e.type!=='step_links').map(e=>`<details><summary>${e.type==='knowledge_source'?'教材来源':escapeHtml(e.subject)} · ${escapeHtml(({source_available:'已保存来源',computed:'受限计算',symbolically_verified:'受限符号计算',unverified:'尚未验证'})[e.status] || '工具范围内结果')}</summary><p>${escapeHtml(e.assumptions || '')}</p>${e.type==='knowledge_source'?(e.details || []).map(s=>`<p>${escapeHtml(s.document_title)} · ${escapeHtml(s.chapter || '')} · 第 ${Number(s.page_start)||'?'} 页</p><blockquote>${escapeHtml(s.content)}</blockquote>`).join(''):`<pre>${escapeHtml(JSON.stringify(e.details,null,2))}</pre>`}</details>`).join('')}</div></details></article>`).join(''):'<div class="library-empty">暂无符合条件的笔记。可从学习回答保存，或新建自己的笔记。</div>';
    visible.forEach(item=>{
      const card=document.querySelector(`[data-note="${item.id}"]`);card.querySelector('[data-note-edit]').onclick=()=>editor(item);
      for(const key of ['favorite','archived']) {
        const button=card.querySelector(key==='favorite'?'[data-note-favorite]':'[data-note-archive]');button.onclick=async()=>{button.disabled=true;try {await request(`/${item.id}`,'PUT',{[key]:!item[key]});await load();} catch(error){showMessage(error.message);button.disabled=false;}};
      }
    });
    $('noteList').querySelectorAll('details').forEach(detail=>detail.addEventListener('toggle',()=>{if(detail.open) typesetMath(detail);}));
  }
  async function load() {
    try {
      const data=await request('');items=data.items;const selected=$('noteCourse').value;
      $('noteCourse').innerHTML='<option value="">全部课程</option>'+[...new Set(items.map(x=>x.course))].sort().map(course=>`<option value="${escapeHtml(course)}">${escapeHtml(course)}</option>`).join('');$('noteCourse').value=selected;render();
    } catch(error) { $('noteList').textContent=error.message; }
  }
  const save=document.createElement('button');save.id='saveAnswerNote';save.type='button';save.className='save-answer-note';save.textContent='保存为学习笔记 ↗';$('answer').parentElement.appendChild(save);
  function sync() {save.disabled=!lastAskResult?.answer_id || Boolean(askController);}
  save.onclick=async()=>{
    const answerId=lastAskResult?.answer_id;if(!answerId)return;save.disabled=true;
    try {const item=await request('','POST',{answer_id:answerId,course:lastAskResult?.knowledge_sources?.[0]?.course || '未分课程'});await load();MathWorkspace.showView('study-notes');editor(item);}
    catch(error){showMessage(error.message);}finally{sync();}
  };
  $('newNote').onclick=()=>editor();$('closeNote').onclick=()=>$('noteDialog').close();
  $('noteForm').onsubmit=async(event)=>{event.preventDefault();$('saveNoteEdit').disabled=true;try {await request(editing?`/${editing.id}`:'',editing?'PUT':'POST',{title:$('noteTitle').value,course:$('noteCourseEdit').value,content:$('noteContent').value});$('noteDialog').close();await load();} catch(error){$('noteStatus').textContent=error.message;}finally{$('saveNoteEdit').disabled=false;}};
  ['noteSearch','noteCourse','noteFilter'].forEach(id=>$(id).addEventListener(id==='noteSearch'?'input':'change',render));
  document.addEventListener('workspacechange',()=>{sync();if(MathWorkspace.view==='study-notes')load();});
  window.MathNotes={sync,load};sync();load();
})();
