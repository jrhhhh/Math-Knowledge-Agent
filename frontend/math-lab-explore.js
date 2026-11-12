/* New experiments share the existing request lifecycle and plotting canvas. */
(() => {
  const $=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=v=>v==null?'未定义':Number(v.toPrecision(6)).toString();
  const parents={taylor:'derivative',sequence:'series',path:'surface',gradient:'surface',system:'system',quadratic:'quadratic',decomposition:'decomposition'};
  const choices={derivative:[['derivative','割线与切线'],['taylor','Taylor 逼近与误差']],series:[['series','数项级数'],['sequence','函数列与误差带']],surface:[['surface','曲面与偏导'],['path','二元极限 · 路径'],['gradient','梯度、等高线与线性平面']]};
  const title={taylor:'Taylor 逼近与误差',sequence:'函数列与误差带',path:'二元极限 · 路径',gradient:'梯度与等高线',system:'方程组与消元',quadratic:'二次型与主轴',decomposition:'分解与迭代'};
  const field=(id,label,value,opts='')=>`<label>${label}<input id="${id}" value="${esc(value)}" ${opts}></label>`;
  const num=(id,label,value,min=-100,max=100,step='any')=>field(id,label,value,`type="number" min="${min}" max="${max}" step="${step}"`);
  const matrix=(id,value='2 1\n1 2')=>`<label>矩阵 A<textarea id="${id}" rows="3" spellcheck="false">${value}</textarea></label>`;
  const forms={
    taylor:field('exploreTaylorExpr','函数 f(x)','sin(x)')+num('exploreTaylorCenter','展开点 c',0,-20,20)+num('exploreTaylorOrder','阶数 m',4,0,12,1)+num('exploreTaylorLeft','区间左端',-3)+num('exploreTaylorRight','区间右端',3),
    sequence:field('exploreSequenceExpr','函数列 fₙ(x)','x^n')+field('exploreSequenceLimit','候选极限函数 f(x)','0')+num('exploreSequenceN','当前 n',10,1,300,1)+num('exploreSequenceEpsilon','误差带 ε',.1,.000001,10)+num('exploreSequenceLeft','区间左端',0)+num('exploreSequenceRight','区间右端',.9)+'<p>支持 x、n。候选极限由你填写，尚未验证；采样误差不等于严格上确界。</p>',
    path:field('explorePathExpr','函数 f(x,y)','x^2*y/(x^4+y^2)')+field('explorePathX','路径 x(t)','t')+field('explorePathY','路径 y(t)','t^2')+'<p>观察趋近原点的路径。试着比较 y(t)=0、t 和 t^2；不同路径可以给出不同结果。</p>',
    gradient:field('exploreGradientExpr','函数 f(x,y)','x^2+y^2')+num('exploreGradientX','观察点 x₀',1)+num('exploreGradientY','观察点 y₀',1)+num('exploreGradientRadius','绘图半径 R',3,.2,100)+num('exploreGradientAngle','单位方向角 θ（度）',30,-180,180)+'<p>曲面叠加线性平面，下方联动显示等高线、偏导向量和所选方向。一般函数的可微性须另外验证。</p>',
    system:`<p class="system-editor-intro">每行就是一个方程，直接修改未知量前的系数和等号右边的数。</p><div class="system-dimensions"><label>方程数<select id="systemRows">${[1,2,3,4].map(n=>`<option ${n===2?'selected':''}>${n}</option>`).join('')}</select></label><label>未知量数<select id="systemCols">${[1,2,3,4].map(n=>`<option ${n===2?'selected':''}>${n}</option>`).join('')}</select></label></div><div id="systemEquationEditor" class="system-equation-editor" aria-label="方程组编辑器"></div><p>蓝、橙等颜色对应图中直线。系数可填负数、小数或分数，例如 −2、0.5、1/3。</p><div hidden>${matrix('exploreSystemMatrix')}${field('exploreSystemRhs','右端向量 b','1 2')}</div>`,
    quadratic:matrix('exploreQuadraticMatrix')+num('exploreQuadraticRadius','绘图半径 R',3,.2,100)+'<p>输入2×2对称矩阵，观察 xᵀAx 的曲面、等高线和主轴。试试 1 0 / 0 -1 的不定情形。</p>',
    decomposition:matrix('exploreDecompositionMatrix','1 1\n0 0.8')+field('exploreDecompositionVector','初始向量 v（两个数）','1 1')+num('exploreDecompositionIterations','迭代步数',8,1,40,1)+`<label>查看实验<select id="exploreDecompositionView"><option value="svd">SVD · 单位圆变换</option><option value="iteration">迭代 · Aᵏv 轨迹</option></select></label>`
  };
  $('labExploreControls').innerHTML=Object.entries(forms).map(([kind,html])=>`<div id="lab-explore-${kind}" hidden><h3>${title[kind]}</h3>${html}</div>`).join('');
  $('labSupplement').innerHTML='';
  $('labPlot').insertAdjacentHTML('beforebegin','<div id="labSystemEquations" class="system-equations-summary" hidden></div>');
  let mode='',lastData=null;
  const numeric=id=>Number($(id).value),text=id=>$(id).value.trim();
  const parseMatrix=id=>text(id).split(/\n|;/).filter(Boolean).map(row=>row.trim().split(/[\s,，]+/));
  function payload(kind){
    const p={kind};const keys={taylor:'Taylor',sequence:'Sequence',path:'Path',gradient:'Gradient',system:'System',quadratic:'Quadratic',decomposition:'Decomposition'};const prefix='explore'+keys[kind];
    for(const el of document.querySelectorAll(`#lab-explore-${kind} input[type=number]`)){
      if(!el.value.trim()||!Number.isFinite(Number(el.value))||!el.checkValidity())throw Error(el.closest('label').childNodes[0].textContent+'：请输入范围内的有效数值');
    }
    if(['taylor','sequence','path','gradient'].includes(kind))p.expression=text(prefix+'Expr');
    if(kind==='taylor')Object.assign(p,{center:numeric(prefix+'Center'),order:numeric(prefix+'Order'),left:numeric(prefix+'Left'),right:numeric(prefix+'Right')});
    if(kind==='sequence')Object.assign(p,{index:numeric(prefix+'N'),epsilon:numeric(prefix+'Epsilon'),limit_expression:text(prefix+'Limit'),left:numeric(prefix+'Left'),right:numeric(prefix+'Right')});
    if(kind==='path')Object.assign(p,{path_x:text(prefix+'X'),path_y:text(prefix+'Y')});
    if(kind==='gradient')Object.assign(p,{x:numeric(prefix+'X'),y:numeric(prefix+'Y'),radius:numeric(prefix+'Radius'),angle:numeric(prefix+'Angle')});
    if(['system','quadratic','decomposition'].includes(kind))p.matrix=parseMatrix(prefix+'Matrix');
    if(kind==='system'){for(const el of document.querySelectorAll('#systemEquationEditor input')){if(!el.value.trim())throw Error('请填写每一项系数和等号右侧的数；没有该项时请填0');}}
    if(kind==='system')p.rhs=text(prefix+'Rhs').split(/[\s,，]+/);
    if(kind==='quadratic')Object.assign(p,{radius:numeric(prefix+'Radius'),x:0,y:0});
    if(kind==='decomposition')Object.assign(p,{vector:text(prefix+'Vector').split(/[\s,，]+/).map(Number),iterations:numeric(prefix+'Iterations')});
    return p;
  }
  const colors=['#347fd7','#cc8b54','#579c88','#8b77ba'];
  function equationText(row,rhs){
    const terms=[];
    row.forEach((raw,index)=>{
      const value=String(raw),negative=value.startsWith('-'),absolute=negative?value.slice(1):value;
      if(Number(absolute)===0)return;
      const coefficient=absolute==='1'?'':absolute.includes('/')?'('+absolute+')':absolute;
      terms.push((terms.length?(negative?' − ':' + '):(negative?'−':''))+coefficient+'x'+['₁','₂','₃','₄'][index]);
    });
    return (terms.join('')||'0')+' = '+rhs;
  }
  function buildSystemEditor(){
    const rows=Number($('systemRows').value),cols=Number($('systemCols').value),A=parseMatrix('exploreSystemMatrix'),b=text('exploreSystemRhs').split(/[\s,，]+/);
    const next=Array.from({length:rows},(_,i)=>Array.from({length:cols},(_,j)=>A[i]?.[j]??(i===j?'1':'0'))),rhs=Array.from({length:rows},(_,i)=>b[i]??'0');
    $('systemEquationEditor').innerHTML=next.map((row,i)=>`<div class="system-equation-row" style="--equation-color:${colors[i%colors.length]}"><span class="system-row-index" aria-label="方程 ${i+1}">${i+1}</span><div class="system-equation-terms">${row.map((value,j)=>`${j?'<span class="system-operator">+</span>':''}<label class="system-term"><input data-system-row="${i}" data-system-col="${j}" value="${esc(value)}" aria-label="方程${i+1}，x${j+1}的系数" spellcheck="false"><span>x<sub>${j+1}</sub></span></label>`).join('')}<span class="system-operator">=</span><input class="system-rhs" data-system-rhs="${i}" value="${esc(rhs[i])}" aria-label="方程${i+1}，等号右侧" spellcheck="false"></div></div>`).join('');
    $('exploreSystemMatrix').value=next.map(row=>row.join(' ')).join('\n');$('exploreSystemRhs').value=rhs.join(' ');
  }
  function syncSystemEditor(){
    const A=Array.from({length:Number($('systemRows').value)},()=>Array(Number($('systemCols').value)).fill('')),b=[];
    document.querySelectorAll('[data-system-col]').forEach(el=>A[Number(el.dataset.systemRow)][Number(el.dataset.systemCol)]=el.value.trim());
    document.querySelectorAll('[data-system-rhs]').forEach(el=>b[Number(el.dataset.systemRhs)]=el.value.trim());
    $('exploreSystemMatrix').value=A.map(row=>row.join(' ')).join('\n');$('exploreSystemRhs').value=b.join(' ');
    $('exploreSystemMatrix').dispatchEvent(new Event('input',{bubbles:true}));
  }
  $('systemEquationEditor').addEventListener('input',syncSystemEditor);
  ['systemRows','systemCols'].forEach(id=>$(id).onchange=()=>{buildSystemEditor();$('exploreSystemMatrix').dispatchEvent(new Event('input',{bubbles:true}));});
  function systemPlot(d){
    const initial=d.steps[0].matrix,labels=d.A.map((row,i)=>equationText(initial[i].slice(0,-1),initial[i].at(-1)));
    let solution=null;
    if(d.status==='唯一解')for(let i=0;i<d.A.length&&!solution;i++)for(let j=i+1;j<d.A.length;j++){
      const [a,b]=d.A[i],[c,e]=d.A[j],det=a*e-b*c;if(det!==0){solution=[(d.b[i]*e-b*d.b[j])/det,(a*d.b[j]-d.b[i]*c)/det];break;}
    }
    const radius=Math.max(5,Math.abs(solution?.[0]||0)*1.4,Math.abs(solution?.[1]||0)*2),scale=250/radius,X=x=>320+x*scale,Y=y=>205-y*scale;
    let out='<title>方程组的直线与公共交点</title><defs><clipPath id="systemPlotClip"><rect x="65" y="50" width="510" height="310"/></clipPath></defs>';
    for(let i=-2;i<=2;i++){const v=radius*i/2;out+=`<path d="M${X(v)} 55V355" stroke="#deebf4"/><text x="${X(v)}" y="380" text-anchor="middle" font-size="11">${fmt(v)}</text>`;}
    out+='<path d="M70 205H570 M320 55V355" stroke="#a0b8ca"/><text x="578" y="210">x₁</text><text x="327" y="48">x₂</text><g clip-path="url(#systemPlotClip)">';
    d.A.forEach(([a,b],i)=>{
      const color=colors[i%colors.length];if(a===0&&b===0)return;
      const p=b!==0?[-radius,(d.b[i]+a*radius)/b]:[d.b[i]/a,-radius],q=b!==0?[radius,(d.b[i]-a*radius)/b]:[d.b[i]/a,radius];
      out+=`<path d="M${X(p[0])} ${Y(p[1])}L${X(q[0])} ${Y(q[1])}" stroke="${color}" stroke-width="2.6"/>`;
    });
    if(solution){const [x,y]=solution;out+=`<circle cx="${X(x)}" cy="${Y(y)}" r="5" fill="#285e89" stroke="white" stroke-width="2"/>`;}
    out+='</g>';
    if(solution){const [x,y]=solution;out+=`<text x="${Math.min(410,Math.max(80,X(x)+12))}" y="${Math.max(70,Y(y)-14)}" font-size="13" fill="#285e89" stroke="#f6faff" stroke-width="4" paint-order="stroke">公共交点 (${fmt(x)}, ${fmt(y)})</text>`;}
    out+=`<text x="70" y="415" font-size="12" fill="#6b869e">${d.status==='无解'?'这些方程没有公共交点':d.status==='无穷多解'?'约束重合或不足：存在无穷多个公共解':'交点同时满足每个方程'}</text>`;
    $('labSystemEquations').innerHTML='<div class="system-equation-heading"><strong>正在求解的方程组</strong><span>与图中颜色一一对应</span></div>'+labels.map((label,i)=>`<div class="system-readable-equation"><i style="background:${colors[i%colors.length]}"></i><span>${esc(label)}</span></div>`).join('');
    return out;
  }

  function chart(curves,{band=0,xLabel='x',fixedExtent=null}={}){
    const finite=curves.flatMap(c=>c.points).filter(p=>p.every(Number.isFinite));
    if(!finite.length)return '<text x="50" y="60">没有有限实数采样值</text>';
    let xmin=Math.min(...finite.map(p=>p[0])),xmax=Math.max(...finite.map(p=>p[0]));
    let ymin=Math.min(0,...finite.map(p=>p[1]))-band,ymax=Math.max(0,...finite.map(p=>p[1]))+band;
    if(fixedExtent){xmin=ymin=-fixedExtent;xmax=ymax=fixedExtent;}
    const dx=xmax-xmin||1,dy=ymax-ymin||1,plotLeft=fixedExtent?167.5:60,plotRight=fixedExtent?472.5:580;
    const X=x=>(fixedExtent?167.5:60)+(x-xmin)/dx*(fixedExtent?305:520),Y=y=>360-(y-ymin)/dy*305;
    let out='<defs><clipPath id="exploreChartClip"><rect x="55" y="45" width="530" height="320"/></clipPath></defs>';
    for(let i=0;i<=5;i++)out+=`<path d="M${plotLeft} ${55+i*61}H${plotRight}" stroke="#dce8f2"/><text x="52" y="${59+i*61}" text-anchor="end" font-size="10">${fmt(ymax-dy*i/5)}</text>`;
    out+=`<path d="M${plotLeft} ${Y(0)}H${plotRight}" stroke="#8daac2"/><text x="${plotLeft}" y="385">${fmt(xmin)}</text><text x="${plotRight}" y="385" text-anchor="end">${fmt(xmax)}</text><text x="580" y="400" text-anchor="end">${esc(xLabel)}</text><g clip-path="url(#exploreChartClip)">`;
    if(band&&curves[1]){
      let segment=[];const flushBand=()=>{if(segment.length>1)out+=`<polygon points="${[...segment.map(([x,y])=>`${X(x)},${Y(y+band)}`),...segment.slice().reverse().map(([x,y])=>`${X(x)},${Y(y-band)}`)].join(' ')}" fill="#5fa78d22"/>`;segment=[];};
      curves[1].points.forEach(p=>{if(p.every(Number.isFinite))segment.push(p);else flushBand();});flushBand();
    }
    curves.forEach((curve,i)=>{let segment=[];const flush=()=>{if(segment.length>1)out+=`<polyline points="${segment.join(' ')}" fill="none" stroke="${colors[i%3]}" stroke-width="2.4"/>`;else if(segment.length===1){const [x,y]=segment[0].split(',');out+=`<circle cx="${x}" cy="${y}" r="3" fill="${colors[i%3]}"/>`;}segment=[];};curve.points.forEach(([x,y])=>{if(!Number.isFinite(y)){flush();return;}segment.push(`${X(x)},${Y(y)}`);});flush();});
    out+='</g>'+curves.map((c,i)=>`<text x="${60+i*175}" y="420" font-size="12" fill="${colors[i%3]}">${esc(c.label)}</text>`).join('');
    return out;
  }
  const formula=(label,latex)=>`<div><span>${esc(label)}</span><div>\\[${esc(latex)}\\]</div></div>`;
  const table=m=>`<table class="lab-step-matrix"><tbody>${m.map(row=>`<tr>${row.map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  const matrixLatex=m=>'\\begin{pmatrix}'+m.map(row=>row.map(fmt).join('&')).join('\\\\')+'\\end{pmatrix}';
  const svg=markup=>`<svg viewBox="0 0 640 440" role="img" aria-label="辅助数学图像">${markup}</svg>`;
  function contours(d){
    const r=d.axis.at(-1),N=d.axis.length,X=x=>320+x/r*165,Y=y=>205-y/r*165;
    let out='<title>等高线与方向</title>';
    for(let k=1;k<8;k++){
      const level=d.z_min+(d.z_max-d.z_min)*k/8;
      for(let j=0;j<N-1;j++)for(let i=0;i<N-1;i++){
        const corners=[[d.axis[i],d.axis[j],d.grid[j][i]],[d.axis[i+1],d.axis[j],d.grid[j][i+1]],[d.axis[i+1],d.axis[j+1],d.grid[j+1][i+1]],[d.axis[i],d.axis[j+1],d.grid[j+1][i]]];
        if(corners.some(p=>p[2]===null))continue;const cuts=[];
        for(let e=0;e<4;e++){const a=corners[e],b=corners[(e+1)%4];if((a[2]<level)!==(b[2]<level)){const t=(level-a[2])/(b[2]-a[2]);cuts.push([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]);}}
        for(let c=0;c+1<cuts.length;c+=2)out+=`<path d="M${X(cuts[c][0])} ${Y(cuts[c][1])}L${X(cuts[c+1][0])} ${Y(cuts[c+1][1])}" stroke="hsl(${215-k*5} 50% 52%)" fill="none"/>`;
      }
    }
    out+='<defs><marker id="contourArrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#c5844d"/></marker></defs>';
    const arrow=(x,y,dx,dy,color)=>`<path d="M${X(x)} ${Y(y)}l${dx*165/r} ${-dy*165/r}" stroke="${color}" stroke-width="2.5" marker-end="url(#contourArrow)"/>`;
    const p=d.point;
    if(mode==='gradient'&&Math.abs(p.x)<=r&&Math.abs(p.y)<=r){
      const length=Math.hypot(p.dx??0,p.dy??0);if(length)out+=arrow(p.x,p.y,p.dx/length*r*.35,p.dy/length*r*.35,'#c5844d');
      out+=arrow(p.x,p.y,d.direction[0]*r*.3,d.direction[1]*r*.3,'#367fd7');
      out+=`<circle cx="${X(p.x)}" cy="${Y(p.y)}" r="4" fill="#c5844d"/>`;
    }
    if(mode==='quadratic')d.orthogonal[0].forEach((_,i)=>{const a=d.orthogonal[0][i],b=d.orthogonal[1][i];out+=`<path d="M${X(-a*r)} ${Y(-b*r)}L${X(a*r)} ${Y(b*r)}" stroke="${colors[i]}" stroke-width="2" stroke-dasharray="6 4"/>`;});
    return out+'<text x="24" y="412" font-size="13">'+(mode==='gradient'?'等高线 · 橙：偏导向量方向；蓝：所选单位方向':'等高线 · 虚线：两个正交主轴')+'</text>';
  }
  function systemView(d,step=0){
    const entry=d.steps[step];$('labSupplement').innerHTML=`<div class="lab-step-controls"><label>消元步骤 <output>${step+1} / ${d.steps.length}</output><input id="exploreSystemStep" type="range" min="0" max="${d.steps.length-1}" value="${step}"></label><strong>${esc(entry.label)}</strong>${table(entry.matrix)}</div>`;
    $('exploreSystemStep').oninput=e=>systemView(d,Number(e.target.value));
    if(d.A[0].length===2)$('labPlot').innerHTML=systemPlot(d);
    else {const initial=d.steps[0].matrix;$('labSystemEquations').innerHTML='<strong>正在求解的方程组</strong>'+initial.map((row,i)=>`<div class="system-readable-equation"><i style="background:${colors[i%colors.length]}"></i><span>${esc(equationText(row.slice(0,-1),row.at(-1)))}</span></div>`).join('');$('labPlot').innerHTML='<text x="40" y="70">此矩阵含 '+d.A[0].length+' 个未知量</text><text x="40" y="105">在下方逐步查看增广矩阵的行变换。</text>';}
  }
  function decompositionView(d,stage=0){
    const view=$('exploreDecompositionView').value;
    if(view==='iteration'){
      $('labPlot').innerHTML=chart([{label:'Aᵏv 轨迹',points:d.trajectory}],{xLabel:'v₁'});
      $('labSupplement').innerHTML=svg(chart([{label:'‖Aᵏv‖₂',points:d.trajectory.map((v,k)=>[k,Math.hypot(...v)])}],{xLabel:'k'}));return;
    }
    const multiply=(m,v)=>m.map(row=>row[0]*v[0]+row[1]*v[1]);
    const circle=Array.from({length:121},(_,i)=>[Math.cos(i*Math.PI/60),Math.sin(i*Math.PI/60)]);
    const transformed=circle.map(v=>{if(stage>0)v=multiply(d.Vt,v);if(stage>1)v=v.map((a,i)=>a*d.singular_values[i]);if(stage>2)v=multiply(d.U,v);return v;});
    $('labPlot').innerHTML=chart([{label:'原单位圆',points:circle},{label:['原始','Vᵀ 后','ΣVᵀ 后','UΣVᵀ = A 后'][stage],points:transformed}],{fixedExtent:Math.max(1,...d.singular_values)*1.3});
    $('labSupplement').innerHTML=`<div class="lab-step-controls"><label>SVD 变换阶段 <output>${['原始','Vᵀ：正交变换','Σ：沿坐标轴伸缩','U：正交变换'][stage]}</output><input id="exploreSvdStage" type="range" min="0" max="3" step="1" value="${stage}"></label></div>`;
    $('exploreSvdStage').oninput=e=>decompositionView(d,Number(e.target.value));
  }
  function render(kind,d){
    mode=kind;lastData=d;$('labSupplement').innerHTML='';$('labFormula').innerHTML='';$('labCondition').textContent=d.note;
    if(['taylor','sequence','path'].includes(kind)){
      $('labPlot').innerHTML=chart(d.curves,{band:d.epsilon||0,xLabel:kind==='path'?'−log₁₀(t)':'x'});
      if(d.error_curve)$('labSupplement').innerHTML=svg(chart([{label:'逐点绝对误差',points:d.error_curve}]));
      if(kind==='taylor'){$('labResult').textContent='采样点最大误差 = '+fmt(d.max_sample_error);$('labFormula').innerHTML=formula('Taylor 多项式',d.polynomial);}
      if(kind==='sequence'){$('labResult').textContent='采样点最大误差 = '+fmt(d.max_sample_error)+' · '+(d.within_band?'当前全部采样点在 ε 带内':'当前未全部落入 ε 带');$('labFormula').innerHTML=formula('当前函数',d.function)+formula('候选极限（未验证）',d.reference);}
      if(kind==='path'){$('labResult').textContent='表格仅显示 t>0 的趋近过程';$('labFormula').innerHTML=formula('路径 (x(t), y(t))',d.path)+formula('沿此路径 t→0⁻ 的极限',d.left_limit)+formula('沿此路径 t→0⁺ 的极限',d.right_limit);$('labSupplement').innerHTML='<div class="lab-scroll"><table class="lab-path-table"><thead><tr><th>t</th><th>x(t)</th><th>y(t)</th><th>f(x(t),y(t))</th></tr></thead><tbody>'+d.table.map(row=>'<tr>'+[row.t,row.x,row.y,row.value].map(v=>`<td>${fmt(v)}</td>`).join('')+'</tr>').join('')+'</tbody></table></div>';}
    }else if(['gradient','quadratic'].includes(kind)){
      window.MathLabExtra.setMode('surface');window.MathLabExtra.render('surface',{...d,show_linear_plane:kind==='gradient'});
      $('labSupplement').innerHTML=svg(contours(d));$('labCondition').textContent=d.note;
      if(kind==='gradient'){$('labResult').textContent+=` · ∇f·u = ${fmt(d.directional_candidate)}（可微时为方向导数）`;}
      else{$('labResult').textContent='二次型：'+d.classification+' · 特征值 '+d.eigenvalues.map(fmt).join('，');$('labFormula').innerHTML=formula('二次型',d.form)+formula('正交矩阵 Q（x=Qu）',matrixLatex(d.orthogonal))+formula('标准形',`${fmt(d.eigenvalues[0])}u_1^2+(${fmt(d.eigenvalues[1])})u_2^2`);}
    }else if(kind==='system'){
      $('labResult').textContent=`${d.status} · rank A = ${d.rank} · rank[A|b] = ${d.augmented_rank}${d.free_variables!==null?' · 自由变量 '+d.free_variables:''}`;
      $('labFormula').innerHTML=d.solution?formula('精确解集',d.solution):'<p>系数矩阵与增广矩阵的秩不同，方程组无解。</p>';systemView(d);
    }else{
      $('labResult').textContent='奇异值 '+d.singular_values.map(fmt).join('，')+' · 谱半径 '+fmt(d.spectral_radius)+' · SVD 重构残差 '+fmt(d.residual);
      $('labFormula').innerHTML=formula('U',matrixLatex(d.U))+formula('Σ',matrixLatex([[d.singular_values[0],0],[0,d.singular_values[1]]]))+formula('Vᵀ',matrixLatex(d.Vt));decompositionView(d);
    }
  }
  $('exploreDecompositionView').onchange=()=>{if(lastData&&mode==='decomposition')decompositionView(lastData);};
  window.MathLabExplore={parents,has:kind=>kind in parents,payload,render,
    configure(kind){if(kind==='system')buildSystemEditor();$('labSystemEquations').hidden=kind!=='system';mode=kind;lastData=null;$('labSupplement').innerHTML='';const parent=parents[kind]||kind,options=choices[parent];$('labExperimentControl').hidden=!options;
      if(options){$('labExperiment').innerHTML=options.map(([value,label])=>`<option value="${value}">${label}</option>`).join('');$('labExperiment').value=kind;}
      Object.keys(forms).forEach(key=>$('lab-explore-'+key).hidden=key!==kind);$('labExploreControls').hidden=!(kind in parents);
    },description(kind){return title[kind]+'\n'+JSON.stringify(payload(kind));},reset(){document.querySelectorAll('#labExploreControls textarea').forEach(el=>el.value=el.defaultValue);$('exploreDecompositionView').value='svd';$('systemRows').value='2';$('systemCols').value='2';buildSystemEditor();}
  };
})();
