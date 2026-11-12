/* Layered galaxy navigation; static decorative paths keep idle rendering at zero. */
(() => {
 const core=window.MathGraphRenderer,root=document.getElementById('graphCanvas'),NS='http://www.w3.org/2000/svg',taxonomy=window.MathGraphTaxonomy;
 let original={nodes:[],edges:[]},colors={},path=[],groups=[],current=null,scopeVersion=0,aiController=null,aiBusy=false,shown=0;
 const shades=['#73ceff','#c4a1ff','#75e1c7','#ffc88a','#f29ac6','#92b9ff','#d9dfaa'];
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const el=(name,attrs={})=>{const n=document.createElementNS(NS,name);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,String(v)));return n;};
 function stars(svg,width=1200,height=650){
  const defs=el('defs');
  const sky=el('radialGradient',{id:'galaxy-sky',cx:'50%',cy:'45%',r:'70%'});sky.append(el('stop',{offset:'0%', 'stop-color':'#13233e'}),el('stop',{offset:'70%','stop-color':'#080f23'}),el('stop',{offset:'100%','stop-color':'#040917'}));
  const haze=el('radialGradient',{id:'galaxy-haze'});haze.append(el('stop',{offset:'0%','stop-color':'#8498dc','stop-opacity':.18}),el('stop',{offset:'45%','stop-color':'#7767ac','stop-opacity':.1}),el('stop',{offset:'100%','stop-color':'#192d4c','stop-opacity':0}));defs.append(sky,haze);svg.prepend(defs);
  const background=el('g',{'pointer-events':'none',class:'galaxy-background'});background.append(el('rect',{width,height,fill:'url(#galaxy-sky)'}),el('ellipse',{cx:width*.5,cy:height*.5,rx:width*.65,ry:height*.2,transform:`rotate(-23 ${width*.5} ${height*.5})`,fill:'url(#galaxy-haze)'}));
  let dust='',bright='';for(let i=0;i<480;i++){const seed=((i+1)*2654435761)>>>0,x=seed%width,y=((seed>>>7)*37)%height;(i%8===0?()=>bright+=`M${x} ${y}h.01`:()=>dust+=`M${x} ${y}h.01`)();}
  background.append(el('path',{d:dust,stroke:'#a6b5d1','stroke-width':1,'stroke-linecap':'round',opacity:.32}),el('path',{d:bright,stroke:'#e3efff','stroke-width':2,'stroke-linecap':'round',opacity:.6}));
  svg.insertBefore(background,defs.nextSibling);
 }
 function nav(){
  const bar=document.createElement('div');bar.className='galaxy-navigation';
  bar.innerHTML=`<div class="galaxy-crumbs"><button data-galaxy-depth="0">知识宇宙</button>${path.map((item,i)=>`<span>›</span><button data-galaxy-depth="${i+1}">${esc(item.name)}</button>`).join('')}</div><div class="galaxy-navigation-actions"><span>${current.nodes.length} 个知识点 · ${current.ai?'AI 分类草案':'导航分组'}</span><button data-galaxy-ai ${aiBusy||current.nodes.length>180||current.nodes.length<4?'disabled':''}>${aiBusy?'AI 正在整理…':current.nodes.length>180?'进入主题后可 AI 细分':'AI 细分主题'}</button></div>`;
  root.prepend(bar);
 }
 function decorateLeaf(){
  const ids=new Set(current.nodes.map(n=>String(n.id))),edges=original.edges.filter(e=>ids.has(String(e.source))&&ids.has(String(e.target)));
  core.render({nodes:current.nodes,edges},colors);const svg=root.querySelector('svg'),v=svg.viewBox.baseVal;
  const old=svg.querySelector(':scope > rect');old?.remove();stars(svg,v.width,v.height);svg.classList.add('galaxy-leaf');nav();
  const help=document.createElement('div');help.className='galaxy-footer-note';help.textContent='点击星辰查看知识点 · 本层只绘制组内关系，其他关系仍在数据库中';root.append(help);shown=current.nodes.length;
 }
 function clusterView(){
  core.clear();const height=groups.length>8?Math.ceil(groups.length/4)*185+100:650;const svg=el('svg',{viewBox:`0 0 1200 ${height}`,role:'img','aria-label':`${current.name}，${groups.length}个分组，共${current.nodes.length}个知识点。点击星系继续探索。`,class:'galaxy-overview'});stars(svg,1200,height);
  const positions=groups.map((_,i)=>{if(groups.length>8)return {x:165+(i%4)*290,y:110+Math.floor(i/4)*185};const angle=-Math.PI/2+i*2*Math.PI/groups.length;return groups.length===1?{x:600,y:320}:{x:600+Math.cos(angle)*410,y:325+Math.sin(angle)*195};});
  const owner=new Map();groups.forEach((g,i)=>g.nodes.forEach(n=>owner.set(String(n.id),i)));const crossing=new Map();original.edges.forEach(e=>{const a=owner.get(String(e.source)),b=owner.get(String(e.target));if(a===undefined||b===undefined||a===b)return;const key=[Math.min(a,b),Math.max(a,b)].join(':');crossing.set(key,(crossing.get(key)||0)+1);});
  const links=el('g',{'pointer-events':'none'});crossing.forEach((count,key)=>{const [a,b]=key.split(':').map(Number),p=positions[a],q=positions[b];const line=el('path',{d:`M${p.x} ${p.y}Q600 325 ${q.x} ${q.y}`,fill:'none',stroke:'#91aad0','stroke-opacity':.12,'stroke-width':Math.min(2,.5+Math.log2(count+1)*.2)});const title=el('title');title.textContent=count+' 条已保存的跨分组关系';line.append(title);links.append(line);});svg.append(links);
  const center=el('text',{x:600,y:320,'text-anchor':'middle',fill:'#748cae','font-size':13,'letter-spacing':5});center.textContent=path.length?'CONSTELLATIONS':'MATHEMATICS';svg.append(center);
  groups.forEach((group,i)=>{
   const p=positions[i],color=shades[i%shades.length],id='galaxy-glow-'+i,gradient=el('radialGradient',{id});gradient.append(el('stop',{offset:'0%','stop-color':color,'stop-opacity':.8}),el('stop',{offset:'15%','stop-color':color,'stop-opacity':.3}),el('stop',{offset:'100%','stop-color':color,'stop-opacity':0}));svg.querySelector('defs').append(gradient);
   const g=el('g',{'data-galaxy-group':i,role:'button',tabindex:0,'aria-label':`进入${group.name}，${group.nodes.length}个知识点`,class:'galaxy-cluster'});
   g.append(el('ellipse',{cx:p.x,cy:p.y,rx:130,ry:55,transform:`rotate(-22 ${p.x} ${p.y})`,fill:`url(#${id})`}));
   let dust='';for(let j=0;j<90;j++){const r=9+Math.sqrt(j/90)*88,angle=j*2.39996+i*.8,x=p.x+Math.cos(angle)*r,y=p.y+Math.sin(angle)*r*.36;dust+=`M${x.toFixed(1)} ${y.toFixed(1)}h.01`;}
   g.append(el('path',{d:dust,stroke:color,'stroke-width':1.6,'stroke-linecap':'round',opacity:.75}),el('circle',{cx:p.x,cy:p.y,r:6,fill:'#f1f7ff'}),el('circle',{cx:p.x,cy:p.y,r:12,fill:color,opacity:.25}));
   const text=el('text',{x:p.x,y:p.y+70,'text-anchor':'middle',fill:'#e4edff','font-size':25});text.textContent=group.name;const count=el('text',{x:p.x,y:p.y+94,'text-anchor':'middle',fill:'#8199bd','font-size':15});count.textContent=group.nodes.length+' 个知识点 · 点击进入';g.append(text,count,el('rect',{x:p.x-140,y:p.y-55,width:280,height:165,fill:'transparent',rx:20}));svg.append(g);
  });
  root.replaceChildren(svg);nav();const list=document.createElement('div');list.className='galaxy-mobile-groups';list.innerHTML=groups.map((group,i)=>`<button data-galaxy-group="${i}"><i style="background:${shades[i%shades.length]}"></i><span>${esc(group.name)}</span><small>${group.nodes.length} ›</small></button>`).join('');root.append(list);
  const note=document.createElement('div');note.className='galaxy-footer-note';note.textContent=current.ai?'AI 细分仅为当前视图的分类草案；未改写知识点或前置关系。':'依据领域与关键词分组 · 星系间连线汇总已保存关系，不代表前置顺序';root.append(note);shown=groups.length;
 }
 function show(){
  const started=performance.now();document.getElementById('graphConceptCard')?.classList.add('hidden');current=path.at(-1)||{name:'知识宇宙',nodes:original.nodes};scopeVersion++;aiController?.abort();aiController=null;aiBusy=false;
  groups=current.children||taxonomy.children(current,path.length);
  if(!path.length&&original.nodes.length<=90)groups=[];
  if(groups.length)clusterView();else decorateLeaf();
  root.dataset.renderer='galaxy-hierarchy';root.dataset.renderMs=(performance.now()-started).toFixed(2);window.GraphExplorer?.refresh();const renderedVersion=scopeVersion;queueMicrotask(()=>{if(renderedVersion!==scopeVersion)return;const status=document.getElementById('graphStatus'),legend=document.getElementById('legend');if(status)status.textContent=`全图 ${original.nodes.length} 个知识点 · 当前 ${groups.length?groups.length+' 个分组':current.nodes.length+' 个知识点'}`;if(legend)legend.innerHTML=groups.length?'<em>星系颜色区分导航分组 · 点击逐层进入 · 分类不是前置关系证明</em>':Object.entries(colors).map(([name,color])=>`<span><i style="background:${color}"></i>${esc(name)}</span>`).join('');});
 }
 function go(index){const group=groups[index];if(!group)return;path.push(group);show();}
 async function analyze(){
  if(aiBusy||current.nodes.length<4||current.nodes.length>180)return;aiBusy=true;const version=scopeVersion;aiController=new AbortController();navRefresh();
  try{const response=await fetch((window.MATH_AGENT_API||'http://127.0.0.1:8000')+'/graph-navigation/suggest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({label:current.name,concept_ids:current.nodes.map(n=>Number(n.id))}),signal:aiController.signal});const data=await response.json();if(version!==scopeVersion)return;if(!response.ok)throw Error(data.detail||'AI 分类失败');const byId=new Map(current.nodes.map(n=>[Number(n.id),n]));current.children=data.groups.map(g=>({name:g.name,nodes:g.concept_ids.map(id=>byId.get(id)).filter(Boolean),ai:true}));current.ai=true;show();}
  catch(error){if(error.name!=='AbortError'&&version===scopeVersion)window.showMessage?.(error.message);}
  finally{if(version===scopeVersion){aiBusy=false;navRefresh();}}
 }
 function navRefresh(){root.querySelector('.galaxy-navigation')?.remove();nav();}
 root.addEventListener('click',event=>{const group=event.target.closest('[data-galaxy-group]'),depth=event.target.closest('[data-galaxy-depth]'),ai=event.target.closest('[data-galaxy-ai]');if(!group&&!depth&&!ai)return;event.preventDefault();event.stopImmediatePropagation();if(group)go(Number(group.dataset.galaxyGroup));if(depth){path=path.slice(0,Number(depth.dataset.galaxyDepth));show();}if(ai)analyze();},true);
 root.addEventListener('keydown',event=>{const group=event.target.closest('[data-galaxy-group]');if(group&&['Enter',' '].includes(event.key)){event.preventDefault();event.stopImmediatePropagation();go(Number(group.dataset.galaxyGroup));}},true);
 // Avoid treating breadcrumbs and clusters as a blank-area drag in the expanded view.
 root.addEventListener('pointerdown',event=>{if(event.target.closest('.galaxy-navigation,.galaxy-mobile-groups,[data-galaxy-group]'))event.stopImmediatePropagation();},true);
 window.MathGraphRenderer={render(graph,palette){const same=original.nodes===graph.nodes;original=graph;colors=palette;if(!same)path=[];show();},refresh:core.refresh,clear(){scopeVersion++;aiController?.abort();path=[];groups=[];current=null;original={nodes:[],edges:[]};core.clear();},get stats(){return {nodes:original.nodes.length,edges:original.edges.length,visible:shown,groups:groups.length,depth:path.length,renderMs:Number(root.dataset.renderMs||0),pendingFrame:core.stats.pendingFrame,aiDraft:Boolean(current?.ai)};}};
})();
