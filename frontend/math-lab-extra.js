/* Extra experiments share the bounded backend and existing SVG plotting surface. */
(() => {
  const byId=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=value=>value==null?'不存在或未定义':Number(value.toPrecision(6)).toString();
  const presets={bowl:'a*x^2+b*y^2',saddle:'a*x^2-b*y^2',gaussian:'a*exp(-b*(x^2+y^2))',wave:'sin(a*x)*cos(b*y)',cone:'a*sqrt(x^2+y^2)'};
  const parameterLabels={bowl:['x² 系数 a','y² 系数 b'],saddle:['x² 系数 a','−y² 系数 b'],gaussian:['峰高 a','集中程度 b'],wave:['x 方向频率 a','y 方向频率 b'],cone:['斜率 a']};
  function syncSurfaceParameters(reset=false){
    const preset=byId('labSurfacePreset').value,expression=byId('labSurfaceExpression').value;
    const names=new Set(expression.match(/[A-Za-z_][A-Za-z_0-9]*/g)||[]);
    let visible=0;
    ['A','B'].forEach((key,index)=>{
      const input=byId('labSurface'+key),label=input.closest('label'),used=names.has(key.toLowerCase());
      label.hidden=!used;input.disabled=!used;if(used)visible++;
      label.querySelector('.lab-parameter-name').textContent=parameterLabels[preset]?.[index]||'系数 '+key.toLowerCase();
      input.min=preset==='gaussian'&&key==='B'?'0.1':'-10';input.max='10';
      if(reset)input.value='1';
      byId('labSurface'+key+'Value').textContent=input.value;
    });
    byId('labSurfaceParameters').hidden=visible===0;
  }
  let mode='derivative',surfaceData=null,zoom=1,drag=null,frame=null;
  const number=id=>Number(byId(id).value);
  const formula=(label,text)=>`<div><span>${label}</span><div>\\[${esc(text)}\\]</div></div>`;
  function payload(kind) {
    if(kind==='series')return {kind:byId('labSeriesKind').value,n:number('labSeriesN'),parameter:number('labSeriesParameter'),expression:byId('labSeriesExpression').value};
    return {expression:byId('labSurfaceExpression').value,radius:number('labSurfaceRadius'),x:number('labSurfaceX'),y:number('labSurfaceY'),a:number('labSurfaceA'),b:number('labSurfaceB'),resolution:31};
  }
  function seriesPlot(data){
    const values=[0,...data.terms,...data.partial_sums,...(data.limit===null?[]:[data.limit])];
    const low=Math.min(...values),high=Math.max(...values),span=high-low||1,n=data.terms.length;
    const X=i=>54+(i-1)/Math.max(1,n-1)*525,Y=v=>365-(v-low)/span*305;
    let out='<title>级数通项与部分和</title>';
    for(let i=0;i<=5;i++){const y=60+i*61;out+=`<path d="M54 ${y}H579" stroke="#e0eaf2"/><text x="46" y="${y+4}" text-anchor="end" font-size="11">${fmt(high-span*i/5)}</text>`;}
    out+=`<path d="M54 ${Y(0)}H579 M54 45V375" stroke="#8eaac0"/><text x="54" y="395">1</text><text x="579" y="395" text-anchor="end">${n}</text><text x="600" y="395">n</text>`;
    if(data.limit!==null)out+=`<path d="M54 ${Y(data.limit)}H579" stroke="#58a58f" stroke-dasharray="5 5"/><text x="580" y="${Y(data.limit)-8}" text-anchor="end" fill="#488d7b">极限 ${fmt(data.limit)}</text>`;
    out+=`<polyline points="${data.partial_sums.map((v,i)=>`${X(i+1)},${Y(v)}`).join(' ')}" fill="none" stroke="#367ee1" stroke-width="2.5"/>`;
    out+=data.terms.map((v,i)=>`<circle cx="${X(i+1)}" cy="${Y(v)}" r="${n>100?1.5:2.5}" fill="#c88d52"/>`).join('');
    byId('labPlot').innerHTML=out;
    byId('labResult').textContent=`S${n} = ${fmt(data.partial_sums[n-1])} · a${n} = ${fmt(data.terms[n-1])}${data.error!==null?' · 与级数和的误差 = '+fmt(data.error):''}`;
    byId('labFormula').innerHTML=formula('从 n=1 开始的通项 aₙ',data.term_latex)+`<p class="lab-series-conclusion">${esc(data.conclusion)}</p>${data.remainder_bound!==null?`<p>交错级数余项界：|R${n}| ≤ ${fmt(data.remainder_bound)}</p>`:''}`;
    byId('labCondition').textContent=(data.converges===null?'自定义级数尚未判定收敛性。':'')+'蓝线：部分和；橙点：通项；绿色虚线：收敛级数的和。判别结论来自所选标准级数的条件，有限项图像本身不是收敛证明。显示数值为浮点近似。';
  }
  function drawSurface(){
    if(mode!=='surface'||!surfaceData)return;
    const d=surfaceData,count=d.axis.length,r=d.axis[count-1],mid=(d.z_max+d.z_min)/2,range=(d.z_max-d.z_min)/2||1;
    ['labSurfaceYaw','labSurfaceTilt'].forEach(id=>window.MathLabMotion?.range(byId(id)));
    const yaw=number('labSurfaceYaw')*Math.PI/180,tilt=number('labSurfaceTilt')*Math.PI/180;
    const project=(x,y,z)=>{const xr=Math.cos(yaw)*x-Math.sin(yaw)*y,yr=Math.sin(yaw)*x+Math.cos(yaw)*y;return {x:320+zoom*165*xr,y:220+zoom*110*(Math.sin(tilt)*yr-Math.cos(tilt)*z),depth:Math.cos(tilt)*yr+Math.sin(tilt)*z};};
    const point=(i,j)=>d.grid[j][i]===null?null:project(d.axis[i]/r,d.axis[j]/r,(d.grid[j][i]-mid)/range);
    const cells=[];
    for(let j=0;j<count-1;j++)for(let i=0;i<count-1;i++){
      const corners=[point(i,j),point(i+1,j),point(i+1,j+1),point(i,j+1)];
      if(corners.some(p=>p===null))continue;
      const height=(d.grid[j][i]+d.grid[j][i+1]+d.grid[j+1][i]+d.grid[j+1][i+1])/4;
      const t=(height-d.z_min)/(d.z_max-d.z_min||1);
      cells.push({depth:corners.reduce((a,p)=>a+p.depth,0)/4,markup:`<polygon points="${corners.map(p=>`${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ')}" fill="hsl(${215-t*45} 60% ${73-t*22}%)" stroke="rgba(37,78,105,.18)" stroke-width=".45"/>`});
    }
    cells.sort((a,b)=>a.depth-b.depth);
    let out='<title>二元函数三维曲面；可拖动旋转、滚轮缩放</title><defs><clipPath id="surfaceClip"><rect x="15" y="15" width="610" height="400"/></clipPath></defs><g clip-path="url(#surfaceClip)">';
    out+=cells.map(c=>c.markup).join('');
    for(const [label,a,b] of [['x',[-1,-1,-1],[1.15,-1,-1]],['y',[-1,-1,-1],[-1,1.15,-1]],['z',[-1,-1,-1],[-1,-1,1.15]]]){
      const p=project(...a),q=project(...b);out+=`<line x1="${p.x}" y1="${p.y}" x2="${q.x}" y2="${q.y}" stroke="#597e9a" stroke-width="1.6"/><text x="${q.x+5}" y="${q.y-5}" fill="#456a88" font-size="14">${label}</text>`;
    }
    const p=d.point;
    if(d.show_linear_plane&&p.z!==null&&p.dx!==null&&p.dy!==null){
      const corners=[[-.4,-.4],[.4,-.4],[.4,.4],[-.4,.4]].map(([u,v])=>project((p.x+u*r)/r,(p.y+v*r)/r,(p.z+p.dx*u*r+p.dy*v*r-mid)/range));
      out+=`<polygon points="${corners.map(q=>`${q.x},${q.y}`).join(' ')}" fill="#dca35c44" stroke="#bd8b50" stroke-width="1.2"/>`;
    }
    if(p.z!==null&&Math.abs(p.x)<=r&&Math.abs(p.y)<=r){const q=project(p.x/r,p.y/r,(p.z-mid)/range);out+=`<circle cx="${q.x}" cy="${q.y}" r="5" fill="#d2804f" stroke="white" stroke-width="2"/><text x="${q.x+9}" y="${q.y-9}" font-size="12">P</text>`;}
    out+='</g><text x="24" y="430" font-size="11" fill="#7390a6">拖动旋转 · 滚轮缩放 · z 轴独立缩放</text>';
    byId('labPlot').innerHTML=out;
  }
  function render(kind,data){
    if(kind==='series'){seriesPlot(data);return;}
    surfaceData=data;drawSurface();
    const p=data.point;
    byId('labResult').textContent=`P(${p.x}, ${p.y}) · f(P) = ${fmt(p.z)} · ∂f/∂x(P) = ${fmt(p.dx)} · ∂f/∂y(P) = ${fmt(p.dy)}`;
    byId('labFormula').innerHTML=formula('曲面 z=f(x,y)',data.function)+formula('x 偏导表达式',data.dx_latex)+formula('y 偏导表达式',data.dy_latex)+`<p>采样高度范围 [${fmt(data.z_min)}, ${fmt(data.z_max)}] · 实数有效点 ${data.valid_points}/${data.total_points}</p>`;
    byId('labCondition').textContent='曲面由实数网格近似绘制，未定义或非实数采样点留空；z 轴独立缩放。橙色 P 标记只在观察点落入绘图区时显示。偏导数不等于整体可微性的证明；图形不替代极限、连续性或极值判别。';
  }
  const redraw=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(drawSurface);};
  ['labSurfaceYaw','labSurfaceTilt'].forEach(id=>byId(id).addEventListener('input',redraw));
  byId('labSurfaceViewReset').onclick=()=>{zoom=1;byId('labSurfaceYaw').value=-35;byId('labSurfaceTilt').value=40;redraw();};
  const plot=byId('labPlot');
  plot.addEventListener('pointerdown',event=>{if(mode!=='surface'||!surfaceData||event.button!==0)return;drag={x:event.clientX,y:event.clientY,yaw:number('labSurfaceYaw'),tilt:number('labSurfaceTilt')};plot.setPointerCapture(event.pointerId);event.preventDefault();});
  plot.addEventListener('pointermove',event=>{if(!drag)return;byId('labSurfaceYaw').value=((drag.yaw+(event.clientX-drag.x)*.5+540)%360)-180;byId('labSurfaceTilt').value=Math.max(15,Math.min(80,drag.tilt+(event.clientY-drag.y)*.3));redraw();});
  for(const event of ['pointerup','pointercancel','lostpointercapture'])plot.addEventListener(event,()=>{drag=null;});
  plot.addEventListener('wheel',event=>{if(mode!=='surface'||!surfaceData)return;event.preventDefault();zoom=Math.max(.55,Math.min(1.7,zoom*Math.exp(-event.deltaY*.001)));redraw();},{passive:false});
  function seriesSettings(){const kind=byId('labSeriesKind').value,input=byId('labSeriesParameter');byId('labSeriesParameterLabel').textContent=kind==='geometric'?'公比 r':kind==='exp'?'展开点参数 x':kind==='custom'?'参数 p':'指数 p';input.min=['p','alternating'].includes(kind)?0:-10;input.max=10;byId('labSeriesCustom').hidden=kind!=='custom';const useParameter=kind!=='custom'||(byId('labSeriesExpression').value.match(/[A-Za-z_][A-Za-z_0-9]*/g)||[]).includes('p');input.closest('label').hidden=!useParameter;input.disabled=!useParameter;}
  window.MathLabExtra={payload,render,setMode(next){syncSurfaceParameters();mode=next;surfaceData=null;drag=null;plot.style.touchAction=next==='surface'?'none':'auto';},invalidate(){drag=null;},description(kind){return kind==='surface'?'z = '+byId('labSurfaceExpression').value:'级数 '+byId('labSeriesKind').selectedOptions[0].textContent+(byId('labSeriesKind').value==='custom'?'，通项 '+byId('labSeriesExpression').value:'')+'，参数 '+number('labSeriesParameter')+'，观察 '+number('labSeriesN')+' 项';},reset(){byId('labSeriesKind').value='geometric';byId('labSurfacePreset').value='bowl';byId('labSurfaceExpression').value=presets.bowl;syncSurfaceParameters(true);seriesSettings();byId('labSeriesNValue').textContent=byId('labSeriesN').value;['A','B'].forEach(key=>byId('labSurface'+key+'Value').textContent=byId('labSurface'+key).value);zoom=1;},onChange(change){
    ['A','B'].forEach(key=>byId('labSurface'+key).addEventListener('input',()=>byId('labSurface'+key+'Value').textContent=byId('labSurface'+key).value));
    byId('labSurfaceExpression').addEventListener('input',()=>syncSurfaceParameters());
    syncSurfaceParameters();
    byId('labSeriesExpression').addEventListener('input',seriesSettings);
    byId('labSeriesKind').onchange=()=>{byId('labSeriesParameter').value=byId('labSeriesKind').value==='geometric'?.5:1;seriesSettings();change();};
    byId('labSeriesN').addEventListener('input',()=>byId('labSeriesNValue').textContent=byId('labSeriesN').value);
    byId('labSurfacePreset').onchange=()=>{const value=presets[byId('labSurfacePreset').value];if(value){byId('labSurfaceExpression').value=value;syncSurfaceParameters(true);change();}else byId('labSurfaceExpression').focus();};
  }};
})();
