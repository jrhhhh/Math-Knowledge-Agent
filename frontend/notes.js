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
  function readingSource(snapshot) {
    if(!snapshot?.document_id)return '';
    return `<p>${escapeHtml(snapshot.title)} · PDF ${Number(snapshot.start)}–${Number(snapshot.end)} 页 · 保存时的文本版本</p><button type="button" data-note-book="${Number(snapshot.document_id)}" data-note-page="${Number(snapshot.start)}">打开教材原页</button>${(snapshot.sources||[]).map(source=>`<p>PDF ${Number(source.page_start)} 页 · 版本 ${escapeHtml(source.content_hash?.slice(0,12))}</p><blockquote>${escapeHtml(source.content)}</blockquote>`).join('')}`;
  }
  function preview(text) {
    return String(text || '').replace(/^#{1,6}\s+/gm,'').replace(/\*\*([^*]+)\*\*/g,'$1').replace(/\s+/g,' ').trim();
  }
  function render() {
    const q=$('noteSearch').value.trim().toLowerCase(),course=$('noteCourse').value,filter=$('noteFilter').value;
    const matchesFilter=x=>filter==='all'||(filter==='archived'?x.archived:filter==='favorite'?x.favorite:!x.archived);
    const visible=items.filter(x=>(!course || x.course===course) && (!q || (x.title+' '+x.content).toLowerCase().includes(q)) && matchesFilter(x));
    $('noteCount').textContent=`共 ${items.length} 篇 · 当前显示 ${visible.length} 篇`;
    const emptyMessage=q||course?'没有找到符合搜索条件的笔记。':filter==='favorite'?'还没有收藏笔记。':filter==='archived'?'还没有归档笔记。':filter==='active'?'当前没有未归档笔记。':'还没有笔记。你可以从学习回答保存，或新建一篇笔记。';
    $('noteList').innerHTML=visible.length?visible.map(x=>`<article class="note-card" data-note="${x.id}"><div class="note-card-heading"><div class="note-title-group"><h3>${escapeHtml(x.title)}</h3><div class="note-badges">${x.favorite?'<span class="note-badge is-favorite">已收藏</span>':''}${x.archived?'<span class="note-badge is-archived">已归档</span>':''}</div></div><span>${escapeHtml(x.course)}</span></div><p class="note-excerpt">${escapeHtml(preview(x.content).slice(0,180))}${preview(x.content).length>180?'…':''}</p><div class="note-actions"><button type="button" data-note-edit>编辑</button><button type="button" data-note-favorite>${x.favorite?'取消收藏':'收藏'}</button><button type="button" data-note-archive>${x.archived?'恢复归档':'归档'}</button><a href="${API}/notes/${x.id}/export" download>导出 ↗</a></div><details><summary>阅读全文与来源</summary><div class="note-full">${renderChatMarkdown(x.content)}</div><div class="note-provenance"><b>${x.origin?.course_message_id?`教材伴读回答 #${x.origin.course_message_id}`:x.answer_id?`原回答 #${x.answer_id}`:'个人手工笔记'}</b><p>笔记可经编辑；以下原始依据保留保存时的版本。</p>${x.origin?.answer?`<details><summary>保存时的原回答</summary><div class="note-full">${renderChatMarkdown(x.origin.answer)}</div></details>`:''}${(x.origin?.evidence || []).filter(e=>e.type!=='structural_quality' && e.type!=='step_links').map(e=>`<details><summary>${e.type==='knowledge_source'?'教材来源':escapeHtml(e.subject)} · ${escapeHtml(({source_available:'已保存来源',computed:'受限计算',symbolically_verified:'受限符号计算',unverified:'尚未验证'})[e.status] || '工具范围内结果')}</summary><p>${escapeHtml(e.assumptions || '')}</p>${e.type==='textbook_reading'?readingSource(e.details):e.type==='knowledge_source'?(e.details || []).map(s=>`<p>${escapeHtml(s.document_title)} · ${escapeHtml(s.chapter || '')} · 第 ${Number(s.page_start)||'?'} 页</p><blockquote>${escapeHtml(s.content)}</blockquote>`).join(''):`<pre>${escapeHtml(JSON.stringify(e.details,null,2))}</pre>`}</details>`).join('')}</div></details></article>`).join(''):`<div class="library-empty">${emptyMessage}</div>`;
    visible.forEach(item=>{
      const card=document.querySelector(`[data-note="${item.id}"]`);card.querySelector('[data-note-edit]').onclick=()=>editor(item);
      for(const key of ['favorite','archived']) {
        const button=card.querySelector(key==='favorite'?'[data-note-favorite]':'[data-note-archive]');button.onclick=async()=>{button.disabled=true;try {await request(`/${item.id}`,'PUT',{[key]:!item[key]});await load();} catch(error){showMessage(error.message);button.disabled=false;}};
      }
    });
    $('noteList').querySelectorAll('[data-note-book]').forEach(button=>button.onclick=()=>{MathWorkspace.showView('course-reader');window.MathCourseReader?.openSource(Number(button.dataset.noteBook),Number(button.dataset.notePage));});
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
  $('noteFilter').value='all';
  ['noteSearch','noteCourse','noteFilter'].forEach(id=>$(id).addEventListener(id==='noteSearch'?'input':'change',render));
  document.addEventListener('workspacechange',()=>{sync();if(MathWorkspace.view==='study-notes')load();});
  window.MathNotes={sync,load};sync();load();
})();
