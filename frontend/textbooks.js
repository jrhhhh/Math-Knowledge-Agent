(() => {
  let book=null,chunk=null,readerRequest=0;
  const drafts=new Map();
  const statuses={draft:'待审核',unreviewed:'待校对',approved:'已审核',rejected:'不采用'};
  async function request(path,method='GET',body) {
    const response=await fetch(`${API}/textbooks${path}`,{method,headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const data=await response.json();if(!response.ok)throw new Error(data.detail || '教材操作失败');return data;
  }
  async function list() {
    try {const response=await fetch(`${API}/knowledge/documents`);const data=await response.json();if(!response.ok)throw new Error(data.detail || '读取失败');
      $('textbookList').innerHTML=data.items.length?data.items.map(x=>`<button type="button" data-book="${x.id}"><b>${escapeHtml(x.title)}</b><small>${escapeHtml(x.course)} · ${escapeHtml(x.chapter || '未分章')} · ${x.chunk_count} 段 · ${statuses[x.review_status] || '待审核'}</small></button>`).join(''):'<div class="library-empty">导入课程 PDF，开始对照阅读与校对。</div>';
      $('textbookList').querySelectorAll('[data-book]').forEach(button=>button.onclick=()=>open(Number(button.dataset.book)));
    }catch(error){$('textbookList').textContent=error.message;}
  }
  async function revisions() {
    const requestedId=chunk.id;const data=await request(`/chunks/${requestedId}/revisions`);if(chunk?.id!==requestedId)return;
    $('chunkRevisionList').innerHTML=data.items.length?data.items.map(x=>`<div><small>${escapeHtml(x.reason || '')} · ${statuses[x.review_status] || '待校对'}</small><button type="button" data-restore-chunk="${x.id}">载入该版本</button></div>`).join(''):'<small>暂无修订记录，第一次校对将保留编辑前原文。</small>';
    $('chunkRevisionList').querySelectorAll('[data-restore-chunk]').forEach(button=>button.onclick=()=>{const item=data.items.find(x=>String(x.id)===button.dataset.restoreChunk);$('readerText').value=item.content;$('readerHeading').value=item.heading || '';$('readerChunkStatus').value='unreviewed';$('readerStatus').textContent='已载入历史版本；请核对后保存，不会立即覆盖当前片段。';});
  }
  function rememberDraft() {
    if(!chunk)return;
    const draft={content:$('readerText').value,heading:$('readerHeading').value,status:$('readerChunkStatus').value};
    const savedStatus=chunk.review_status==='draft'?'unreviewed':chunk.review_status;
    if(draft.content!==chunk.content || draft.heading!==(chunk.heading || '') || draft.status!==savedStatus)drafts.set(chunk.id,draft);else drafts.delete(chunk.id);
  }
  function preview() {$('readerMathPreview').textContent=$('readerText').value;typesetMath($('readerMathPreview'));}
  async function page() {
    chunk=book.chunks.find(x=>String(x.id)===$('readerPage').value);if(!chunk)return;
    const draft=drafts.get(chunk.id);
    $('readerText').value=draft?.content ?? chunk.content;$('readerHeading').value=draft?.heading ?? chunk.heading ?? '';$('readerChunkStatus').value=draft?.status ?? (chunk.review_status==='draft'?'unreviewed':chunk.review_status);
    $('readerMathPreview').textContent='';$('readerStatus').textContent=draft?'已恢复当前页面中尚未保存的校对草稿。请核对后保存。':chunk.content?'请对照原页核对文字、公式与必要条件。':'未提取到文字层，可能是扫描页。请对照原页补录文字与公式；不会自动判为已审核。';
    $('originalPdf').hidden=!book.has_original;$('originalPdfUnavailable').hidden=book.has_original;$('originalPdfLink').hidden=!book.has_original;
    if(book.has_original){const url=`${API}/textbooks/${book.id}/file?reader_page=${chunk.page_start}#page=${chunk.page_start}&view=FitH`;$('originalPdf').src=url;$('originalPdfLink').href=url;}
    try {await revisions();}catch(error){$('chunkRevisionList').textContent=error.message;}
  }
  async function open(id) {
    rememberDraft();const requestedVersion=++readerRequest;
    try {const loaded=await request(`/${id}`);if(requestedVersion!==readerRequest)return;book=loaded;$('textbookReader').hidden=false;$('readerTitle').textContent=book.title;$('readerDocumentTitle').value=book.title;$('readerCourse').value=book.course;$('readerChapter').value=book.chapter || '';$('readerDocumentStatus').value=book.review_status==='unreviewed'?'draft':book.review_status;
      $('readerPage').innerHTML=book.chunks.map(x=>`<option value="${x.id}">第 ${x.page_start || '?'} 页 · ${statuses[x.review_status] || '待校对'}</option>`).join('');await page();
    }catch(error){$('readerStatus').textContent=error.message;}
  }
  document.querySelectorAll('[data-library-view]').forEach(button=>button.onclick=()=>{const textbooks=button.dataset.libraryView==='textbooks';document.querySelectorAll('[data-library-view]').forEach(x=>x.setAttribute('aria-pressed',String(x===button)));document.querySelectorAll('#knowledge-library > .library-intro,#knowledge-library > .library-workbench').forEach(x=>x.classList.toggle('workspace-hidden',textbooks));$('textbookWorkspace').classList.toggle('workspace-hidden',!textbooks);if(textbooks)list();});
  $('openTextbookImport').onclick=()=>$('textbookImportDialog').showModal();$('closeTextbookImport').onclick=()=>$('textbookImportDialog').close();
  $('textbookImportForm').onsubmit=async(event)=>{event.preventDefault();const file=$('importBookFile').files[0];if(!file)return;$('submitTextbookImport').disabled=true;$('textbookImportStatus').textContent='正在提取文字，请等待…';
    try {if(file.size>50*1024*1024)throw new Error('文件超过 50 MB，请分章导入');const query=new URLSearchParams({title:$('importBookTitle').value,course:$('importBookCourse').value,chapter:$('importBookChapter').value});const response=await fetch(`${API}/textbooks/upload?${query}`,{method:'POST',headers:{'Content-Type':'application/pdf'},body:file});const data=await response.json();if(!response.ok)throw new Error(data.detail || '导入失败');$('textbookImportDialog').close();await list();await open(data.id);$('readerStatus').textContent=`${data.message}${data.empty_pages?` ${data.empty_pages} 页没有文字层，请对照补录。`:''}`;}
    catch(error){$('textbookImportStatus').textContent=error.message;}finally{$('submitTextbookImport').disabled=false;}};
  $('readerPage').onchange=()=>{rememberDraft();page();};
  ['readerText','readerHeading','readerChunkStatus'].forEach(id=>$(id).addEventListener(id==='readerChunkStatus'?'change':'input',()=>{rememberDraft();if(drafts.has(chunk?.id))$('readerStatus').textContent='校对草稿尚未保存；切换页码会在当前页面中保留。';}));$('previewReaderMath').onclick=preview;
  $('saveDocumentReview').onclick=async(event)=>{event.target.disabled=true;try {const changed=await request(`/${book.id}`,'PUT',{title:$('readerDocumentTitle').value,course:$('readerCourse').value,chapter:$('readerChapter').value,review_status:$('readerDocumentStatus').value});if(book?.id===changed.id){Object.assign(book,changed);$('readerTitle').textContent=changed.title;}await list();$('readerStatus').textContent='教材信息与审核状态已保存；片段仍按各自审核状态使用。';}catch(error){$('readerStatus').textContent=error.message;}finally{event.target.disabled=false;}};
  $('saveChunkReview').onclick=async(event)=>{
    if(!chunk)return;
    const target=chunk,payload={content:$('readerText').value,heading:$('readerHeading').value,review_status:$('readerChunkStatus').value};
    event.target.disabled=true;
    try {
      const data=await request(`/chunks/${target.id}`,'PUT',payload);Object.assign(target,data);
      if(chunk?.id===target.id){rememberDraft();await revisions();const option=[...$('readerPage').options].find(x=>String(x.value)===String(target.id));if(option)option.textContent=`第 ${target.page_start} 页 · ${statuses[data.review_status]}`;preview();$('readerStatus').textContent=drafts.has(target.id)?'上一版校对已保存；当前新增编辑仍是草稿。':'校对已保存，编辑前版本保留在修订记录中。';}
    }catch(error){$('readerStatus').textContent=error.message;}finally{event.target.disabled=false;}
  };
  $('askReadingSelection').onclick=()=>{
    if(askController){$('readerStatus').textContent='请先等待当前回答完成或取消。';return;}
    const text=$('readerText'),selection=text.value.slice(text.selectionStart,text.selectionEnd).trim();
    if(!selection){$('readerStatus').textContent='请先在教材文本框中选中要提问的一段。';return;}
    if(selection.length>6000){$('readerStatus').textContent='选段较长，请缩小到 6000 字以内。';return;}
    MathWorkspace.setMode('explain');MathWorkspace.showView('ask');$('question').value=`教材：${book.title} · ${book.course} · ${book.chapter || '未分章'} · PDF 第 ${chunk.page_start} 页（片段${text.value===chunk.content?statuses[chunk.review_status]:'个人校对草稿，未保存'}；教材${statuses[book.review_status]}）\n选段：\n${selection}\n\n问题：${$('readerQuestion').value.trim() || '请解释这段内容的条件、推理和含义。'}`;$('question').dispatchEvent(new Event('input',{bubbles:true}));$('question').focus();
  };
})();
