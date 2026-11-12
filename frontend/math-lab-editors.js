/* Visual matrix inputs preserve the existing textarea/API contracts. */
(() => {
  const $=id=>document.getElementById(id),esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const configs=[{id:'labMatrixInput',variable:true},{id:'exploreQuadraticMatrix',symmetric:true},{id:'exploreDecompositionMatrix'}];
  function sync(config,force=false){
    const source=$(config.id),editor=$(config.id+'Editor');
    if(!force&&editor.dataset.source===source.value)return;
    const rows=source.value.trim().split(/\n|;/).filter(Boolean).map(r=>r.trim().split(/[\s,，]+/)),size=config.variable?Math.max(1,Math.min(4,rows.length)):2;
    editor.dataset.size=size;
    editor.innerHTML=(config.variable?`<label class="matrix-size-label">矩阵阶数<select class="matrix-size" aria-label="矩阵阶数">${[1,2,3,4].map(n=>`<option ${n===size?'selected':''}>${n}</option>`).join('')}</select></label>`:'')+`<div class="matrix-entry-scroll"><div class="matrix-entry-expression"><span class="matrix-symbol">A =</span><div class="matrix-entry-brackets"><div class="matrix-entry-grid" style="--matrix-size:${size}">${Array.from({length:size},(_,r)=>Array.from({length:size},(_,c)=>`<input data-row="${r}" data-col="${c}" value="${esc(rows[r]?.[c]??'0')}" aria-label="矩阵第${r+1}行第${c+1}列" spellcheck="false" placeholder="a${r+1}${c+1}">`).join('')).join('')}</div></div></div></div><p class="matrix-editor-help">${config.symmetric?'非对角元素同步填写，保持矩阵对称。':'每格填写一个元素，支持负数、小数和分数。'}</p>`;
    editor.dataset.source=source.value;
  }
  function update(config){
    const editor=$(config.id+'Editor'),size=Number(editor.dataset.size),rows=Array.from({length:size},()=>Array(size).fill(''));
    editor.querySelectorAll('[data-row]').forEach(el=>rows[Number(el.dataset.row)][Number(el.dataset.col)]=el.value.trim());
    const source=$(config.id);source.value=rows.map(row=>row.join(' ')).join('\n');editor.dataset.source=source.value;source.dispatchEvent(new Event('input',{bubbles:true}));
  }
  configs.forEach(config=>{
    const source=$(config.id),wrapper=document.createElement('div');wrapper.id=config.id+'Editor';wrapper.className='visual-matrix-editor';wrapper.setAttribute('role','group');wrapper.setAttribute('aria-label','矩阵 A 逐格编辑');source.closest('label').before(wrapper);source.closest('label').hidden=true;
    wrapper.addEventListener('input',event=>{const cell=event.target;if(!cell.matches('[data-row]'))return;
      if(config.symmetric&&cell.dataset.row!==cell.dataset.col){const mirror=wrapper.querySelector(`[data-row="${cell.dataset.col}"][data-col="${cell.dataset.row}"]`);mirror.value=cell.value;}
      update(config);
    });
    wrapper.addEventListener('change',event=>{if(!event.target.matches('.matrix-size'))return;const size=Number(event.target.value),current=Array.from({length:Number(wrapper.dataset.size)},()=>[]);wrapper.querySelectorAll('[data-row]').forEach(cell=>current[Number(cell.dataset.row)][Number(cell.dataset.col)]=cell.value);source.value=Array.from({length:size},(_,r)=>Array.from({length:size},(_,c)=>current[r]?.[c]??'0').join(' ')).join('\n');sync(config,true);source.dispatchEvent(new Event('input',{bubbles:true}));});
    sync(config);
  });
  window.MathLabEditors={sync(force=false){configs.forEach(config=>sync(config,force));},validate(mode){const id={linear:'labMatrixInput',quadratic:'exploreQuadraticMatrix',decomposition:'exploreDecompositionMatrix'}[mode];if(!id)return;for(const input of $(id+'Editor').querySelectorAll('[data-row]'))if(!input.value.trim())throw Error('请填写矩阵每一格，没有该项时请填0');}};
  const layout=document.querySelector('#math-lab .lab-layout'),grip=document.createElement('div');
  grip.className='lab-panel-resizer';grip.tabIndex=0;grip.setAttribute('role','separator');grip.setAttribute('aria-orientation','vertical');grip.setAttribute('aria-label','拖动调整参数面板宽度；方向键微调，双击恢复');grip.setAttribute('aria-controls','labExploreControls');grip.title='拖动调整宽度 · 双击恢复';grip.innerHTML='<span></span>';layout.querySelector('.lab-controls').after(grip);
  let preferred=320,drag=null;
  function bounds(){return {min:260,max:Math.max(260,Math.min(680,layout.clientWidth-314))};}
  function width(value){const b=bounds(),w=Math.round(Math.min(b.max,Math.max(b.min,value)));layout.style.setProperty('--lab-control-width',w+'px');grip.setAttribute('aria-valuemin',b.min);grip.setAttribute('aria-valuemax',b.max);grip.setAttribute('aria-valuenow',w);return w;}
  grip.addEventListener('pointerdown',event=>{if(event.button!==0)return;drag={x:event.clientX,width:layout.querySelector('.lab-controls').getBoundingClientRect().width};grip.setPointerCapture(event.pointerId);layout.classList.add('lab-resizing');event.preventDefault();});
  grip.addEventListener('pointermove',event=>{if(drag)preferred=width(drag.width+event.clientX-drag.x);});
  function release(){drag=null;layout.classList.remove('lab-resizing');}
  ['pointerup','pointercancel','lostpointercapture'].forEach(name=>grip.addEventListener(name,release));
  grip.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const b=bounds();preferred=width(event.key==='Home'?b.min:event.key==='End'?b.max:Number(grip.getAttribute('aria-valuenow'))+(event.key==='ArrowRight'?20:-20));});
  grip.addEventListener('dblclick',()=>{preferred=320;width(preferred);});
  new ResizeObserver(()=>{width(preferred);grip.tabIndex=matchMedia('(min-width:801px)').matches?0:-1;}).observe(layout);width(preferred);
})();
