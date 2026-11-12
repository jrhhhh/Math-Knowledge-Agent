/* Purposeful local feedback. Never animate numerical geometry between results. */
(() => {
  const root=document.getElementById('math-lab'),$=id=>document.getElementById(id);
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let feedbackTimer,frame;
  const animated=new WeakMap();
  function enter(element,keyframes,duration=240){
    if(!element||reduced.matches||!element.animate)return;
    animated.get(element)?.cancel();
    const animation=element.animate(keyframes,{duration,easing:'cubic-bezier(.22,.8,.25,1)'});
    animated.set(element,animation);
  }
  const segments=[...root.querySelectorAll('.lab-subject-tabs,.lab-analysis-tabs')];
  segments.forEach(group=>{group.classList.add('lab-motion-segment');const thumb=document.createElement('span');thumb.className='lab-segment-indicator';thumb.setAttribute('aria-hidden','true');group.prepend(thumb);});
  function syncSegments(){
    cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>segments.forEach(group=>{
      if(group.hidden||!group.getClientRects().length)return;
      const selected=group.querySelector('button[aria-pressed="true"]');if(!selected)return;
      const rect=selected.getBoundingClientRect(),box=group.getBoundingClientRect(),thumb=group.querySelector('.lab-segment-indicator');
      thumb.style.width=rect.width+'px';thumb.style.height=rect.height+'px';thumb.style.transform=`translate(${rect.left-box.left-group.clientLeft}px,${rect.top-box.top-group.clientTop}px)`;
      thumb.classList.add('is-positioned');
    }));
  }
  const resize=new ResizeObserver(syncSegments);segments.forEach(el=>resize.observe(el));
  const pill=document.createElement('div');pill.className='lab-feedback-pill';pill.hidden=true;pill.setAttribute('aria-hidden','true');
  pill.innerHTML='<span class="lab-feedback-symbol"></span><span class="lab-feedback-copy"></span>';
  root.querySelector('.lab-canvas').append(pill);
  function state(next){
    clearTimeout(feedbackTimer);root.dataset.feedback=next;
    const busy=next==='loading';if(busy)root.querySelectorAll('input[type=range]').forEach(range);$('labPlot').setAttribute('aria-busy',String(busy));
    $('labCompute').setAttribute('aria-busy',String(busy));
    $('labCompute').textContent=busy?'正在计算…':'计算并绘图';
    $('labStatus').dataset.state=next;
    if(next==='waiting'){pill.hidden=true;return;}
    const messages={loading:'正在更新图像',success:'图像已更新',warning:'请留意计算条件',error:'输入需要调整'};
    pill.querySelector('.lab-feedback-copy').textContent=messages[next]||'';pill.dataset.state=next;pill.hidden=false;
    enter(pill,[{opacity:0,transform:'translateY(-5px) scale(.97)'},{opacity:1,transform:'translateY(0) scale(1)'}],200);
    if(!busy)feedbackTimer=setTimeout(()=>pill.hidden=true,next==='success'?1500:3000);
    if(next==='success'||next==='warning')enter($('labResult'),[{opacity:.35},{opacity:1}],280);
  }
  function range(input){
    const min=Number(input.min||0),max=Number(input.max||100),percent=max>min?(Number(input.value)-min)/(max-min)*100:0;
    input.style.setProperty('--range-progress',Math.max(0,Math.min(100,percent))+'%');
  }
  root.querySelectorAll('input[type=range]').forEach(range);
  root.addEventListener('input',event=>{const input=event.target;if(input.matches('input[type=range]')){range(input);input.closest('label')?.classList.add('lab-adjusting');}});
  const release=()=>root.querySelectorAll('.lab-adjusting').forEach(el=>el.classList.remove('lab-adjusting'));
  window.addEventListener('pointerup',release);window.addEventListener('pointercancel',release);root.addEventListener('focusout',release);root.addEventListener('keyup',release);
  const localSteps=new MutationObserver(()=>root.querySelectorAll('#labSupplement input[type=range]').forEach(range));
  localSteps.observe($('labSupplement'),{childList:true,subtree:true});
  reduced.addEventListener('change',()=>{root.querySelectorAll('*').forEach(el=>animated.get(el)?.cancel());syncSegments();});
  window.MathLabMotion={state,range,switch(){syncSegments();enter(root.querySelector('.lab-controls'),[{opacity:.4,transform:'translateY(5px)'},{opacity:1,transform:'translateY(0)'}]);},reset(){root.querySelectorAll('input[type=range]').forEach(range);},sync:syncSegments};
  syncSegments();
})();
