(() => {
  const C=MathLabCore, svg=$('labPlot');let mode='derivative';
  const format=n=>n===null?'不存在':Number(n.toFixed(6)).toString();
  const number=id=>Number($(id).value);
  function line(x1,y1,x2,y2,color,width=2,dash='') {return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="${width}" ${dash?`stroke-dasharray="${dash}"`:''}/>`;}
  function draw() {
    const key=$('labFunction').value,e=C.examples[key];let shapes='',result='',condition=e.condition;
    let extent=mode==='linear'?8:6;
    if(mode!=='linear') {const xmax=mode==='derivative'?Math.max(Math.abs(number('labX')),Math.abs(number('labX')+number('labH'))):Math.max(Math.abs(number('labA')),Math.abs(number('labB')));extent=Math.max(6,Math.abs(xmax)+1,Math.abs(e.f(xmax))+1,Math.abs(e.f(-xmax))+1);}
    const X=x=>320+(mode==='linear'?180:270)*x/extent,Y=y=>220-180*y/extent;
    for(let i=-5;i<=5;i++){const p=i*extent/5;shapes+=line(X(p),40,X(p),400,'#dce7f4',1)+line(50,Y(p),590,Y(p),'#dce7f4',1);}
    shapes+=line(50,Y(0),590,Y(0),'#95acc6')+line(X(0),40,X(0),400,'#95acc6');
    shapes+=`<text x="592" y="${Y(0)-8}">x</text><text x="${X(0)+8}" y="32">y</text><text x="${X(-extent)}" y="414">−${format(extent)}</text><text x="${X(extent)}" y="414">${format(extent)}</text>`;
    if(mode==='linear') {
      const m=['labM11','labM12','labM21','labM22'].map(number),v=[number('labV1'),number('labV2')],w=C.transform(m,v),det=C.determinant(m);
      // Fit both the transformed grid and vector without clipping large valid values.
      const largest=Math.max(8,3*(Math.abs(m[0])+Math.abs(m[1])),3*(Math.abs(m[2])+Math.abs(m[3])),...w.map(Math.abs));
      if(largest>extent){extent=largest+1;shapes='';for(let i=-5;i<=5;i++){shapes+=line(X(i),Y(-5),X(i),Y(5),'#dce7f4',1)+line(X(-5),Y(i),X(5),Y(i),'#dce7f4',1);}shapes+=line(30,Y(0),610,Y(0),'#95acc6')+line(X(0),20,X(0),420,'#95acc6');}
      for(let i=-3;i<=3;i++){let a=C.transform(m,[i,-3]),b=C.transform(m,[i,3]);shapes+=line(X(a[0]),Y(a[1]),X(b[0]),Y(b[1]),'#75b7bd',1);a=C.transform(m,[-3,i]);b=C.transform(m,[3,i]);shapes+=line(X(a[0]),Y(a[1]),X(b[0]),Y(b[1]),'#75b7bd',1);}
      const corners=[[0,0],[m[0],m[2]],[m[0]+m[1],m[2]+m[3]],[m[1],m[3]]];shapes+=`<polygon points="${corners.map(p=>`${X(p[0])},${Y(p[1])}`).join(' ')}" fill="#6bafba33" stroke="#5b9fac"/>`;
      shapes+=line(X(0),Y(0),X(v[0]),Y(v[1]),'#377ddd',3)+line(X(0),Y(0),X(w[0]),Y(w[1]),'#bc7853',3)+`<circle cx="${X(w[0])}" cy="${Y(w[1])}" r="5" fill="#bc7853"/>`;
      result=`A = [${format(m[0])}, ${format(m[1])}; ${format(m[2])}, ${format(m[3])}] · v = (${format(v[0])}, ${format(v[1])}) · Av = (${format(w[0])}, ${format(w[1])}) · det A = ${format(det)}。${det===0?'矩阵奇异，平面被压缩为线或点。':`单位正方形面积变为 ${format(Math.abs(det))}；${det<0?'方向翻转。':'方向保持。'}`}`;
      condition='二维实矩阵作用于列向量；图示与读数使用浮点运算。蓝色是原向量，棕色是变换后的向量，青色是变换后的网格。';
    } else {
      if(mode==='integral') {const a=number('labA'),b=number('labB'),n=number('labN'),r=C.integral(key,a,b,n);for(const q of r.rectangles){shapes+=`<rect x="${Math.min(X(q.x),X(q.x+q.dx))}" y="${Math.min(Y(0),Y(q.y))}" width="${Math.abs(X(q.x+q.dx)-X(q.x))}" height="${Math.abs(Y(q.y)-Y(0))}" fill="${q.y>=0?'#71a6ee55':'#dd986955'}" stroke="#6d9fd655"/>`;}
        result=`∫₍${format(a)}₎⁽${format(b)}⁾ ${e.label} dx = ${format(r.exact)}；中点矩形和 (${n} 份) = ${format(r.sum)}；误差 = ${format(Math.abs(r.sum-r.exact))}。`;
        condition+=' 定积分为带符号累积量，反向上下限会改变符号；矩形和为近似值，解析公式读数也按浮点显示。';
      }
      let points=[];for(let i=0;i<=360;i++){const x=-extent+2*extent*i/360,y=e.f(x);if(Math.abs(y)<=extent)points.push(`${X(x)},${Y(y)}`);else if(points.length){shapes+=`<polyline points="${points.join(' ')}" fill="none" stroke="#377ddd" stroke-width="3"/>`;points=[];}}
      if(points.length)shapes+=`<polyline points="${points.join(' ')}" fill="none" stroke="#377ddd" stroke-width="3"/>`;
      if(mode==='derivative') {const x=number('labX'),h=number('labH'),r=C.derivative(key,x,h),ray=(s,color,dash)=>line(X(-extent),Y(r.y+s*(-extent-x)),X(extent),Y(r.y+s*(extent-x)),color,2,dash);
        shapes+=ray(r.secant,'#bc7853','7 5');if(r.tangent!==null)shapes+=ray(r.tangent,'#559b98','');
        shapes+=`<circle cx="${X(x)}" cy="${Y(r.y)}" r="5" fill="#377ddd"/><circle cx="${X(x+h)}" cy="${Y(r.end)}" r="5" fill="#bc7853"/>`;
        result=`x₀ = ${format(x)} · h = ${format(h)} · 割线斜率 = ${format(r.secant)} · 导数 = ${format(r.tangent)}。`;
        condition+=' 棕色虚线为割线，青色为切线；单个 h 的差商不能证明导数存在。';
      }
    }
    svg.innerHTML=`<title>${mode==='linear'?'二维线性变换':mode==='integral'?'积分矩形和':'导数的割线与切线'}</title><defs><clipPath id="labClip"><rect x="30" y="20" width="580" height="400"/></clipPath></defs><g clip-path="url(#labClip)">${shapes}</g>`;
    $('labResult').textContent=result;$('labCondition').textContent=condition;
    ['labX','labH','labA','labB','labN'].forEach(id=>{const out=document.querySelector(`[data-lab-value="${id}"]`);if(out)out.textContent=$(id).value;});
  }
  function choose(next){mode=next;document.querySelectorAll('[data-lab-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.labMode===mode)));$('labFunctionControl').hidden=mode==='linear';['derivative','integral','linear'].forEach(k=>$( `lab-${k}`).hidden=k!==mode);draw();}
  document.querySelectorAll('[data-lab-mode]').forEach(b=>b.onclick=()=>choose(b.dataset.labMode));
  document.querySelectorAll('#math-lab input,#math-lab select').forEach(input=>input.addEventListener('input',draw));
  $('labReset').onclick=()=>{document.querySelectorAll('#math-lab input').forEach(i=>i.value=i.defaultValue);$('labFunction').value='square';draw();};
  $('labToStudy').onclick=()=>{if(askController){showMessage('请等待当前回答结束或取消。');return;}MathWorkspace.setMode('explain');$('question').value=`请解释这个数学实验，并说明适用条件：\n${$('labResult').textContent}\n${$('labCondition').textContent}`;$('question').dispatchEvent(new Event('input',{bubbles:true}));$('question').focus();};
  choose(mode);
})();
