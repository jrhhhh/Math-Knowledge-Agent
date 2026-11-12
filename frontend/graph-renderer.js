/* Bounded static SVG renderer: no per-edge animation, no force simulation. */
(() => {
 const root=document.getElementById('graphCanvas'),NS='http://www.w3.org/2000/svg';
 let svg=null,nodes=[],byId=new Map(),points=new Map(),adjacent=new Map(),ranked=[],base=null,focused=null,frame=0,revision=0;
 const el=(name,attrs={})=>{const node=document.createElementNS(NS,name);Object.entries(attrs).forEach(([k,v])=>node.setAttribute(k,String(v)));return node;};
 function drawLabels(){
  frame=0;if(!svg?.isConnected||!root.getClientRects().length)return;
  const v=svg.viewBox.baseVal,scale=base.width/v.width,rect=svg.getBoundingClientRect(),pixels=Math.min(rect.width/v.width,rect.height/v.height);
  const available=ranked.filter(n=>{const p=points.get(String(n.id));return p.x>=v.x&&p.x<=v.x+v.width&&p.y>=v.y&&p.y<=v.y+v.height;});
  const limit=nodes.length<=70?70:scale>2?100:18,labels=svg.querySelector('.fast-graph-labels'),fragment=document.createDocumentFragment();
  const occupied=[];
  for(const node of available){
   const p=points.get(String(node.id)),name=String(node.name||node.id),label=name.length>16?name.slice(0,16)+'…':name;
   const textWidth=[...label].reduce((sum,char)=>sum+(char.charCodeAt(0)>255?11:6),0),x=p.x*pixels,y=p.y*pixels+12;
   const box={left:x-textWidth/2-5,right:x+textWidth/2+5,top:y-12,bottom:y+5};
   if(occupied.some(b=>box.left<b.right&&box.right>b.left&&box.top<b.bottom&&box.bottom>b.top))continue;occupied.push(box);
   const text=el('text',{x:p.x,y:p.y+12/Math.max(pixels,.01),'text-anchor':'middle','font-size':11/Math.max(pixels,.01)});text.textContent=label;fragment.append(text);if(fragment.childNodes.length>=limit)break;
  }
  labels.replaceChildren(fragment);
 }
 function refresh(){if(!frame)frame=requestAnimationFrame(drawLabels);}
 const observer=new MutationObserver(refresh);
 function highlight(id){
  if(!svg)return;focused=id;const group=svg.querySelector('.fast-graph-focus');group.replaceChildren();if(!id)return;
  const p=points.get(id),node=byId.get(id);if(!p||!node)return;const view=svg.viewBox.baseVal,rect=svg.getBoundingClientRect(),pixelScale=Math.max(.01,Math.min(rect.width/view.width,rect.height/view.height)),offset=12/pixelScale;
  const path=(adjacent.get(id)||[]).map(other=>{const q=points.get(other);return `M${p.x} ${p.y}L${q.x} ${q.y}`;}).join('');
  group.append(el('path',{d:path,stroke:'#b4e4ff','stroke-width':1.5,fill:'none','vector-effect':'non-scaling-stroke'}),el('circle',{cx:p.x,cy:p.y,r:9/pixelScale,stroke:'#e4f5ff','stroke-width':2,fill:'none','vector-effect':'non-scaling-stroke'}));
  const text=el('text',{x:p.x+(p.x>view.x+view.width*.6?-offset:offset),y:p.y-offset,'text-anchor':p.x>view.x+view.width*.6?'end':'start','font-size':13/pixelScale,fill:'#fff','paint-order':'stroke',stroke:'#07111f','stroke-width':5});text.textContent=node.name;group.append(text);
 }
 root.addEventListener('pointerover',event=>{const target=event.target.closest('[data-graph-node-id]');if(target)highlight(target.dataset.graphNodeId);});
 root.addEventListener('pointerout',event=>{if(event.target.closest('[data-graph-node-id]')&&!event.relatedTarget?.closest?.('[data-graph-node-id]'))highlight(null);});
 root.addEventListener('focusin',event=>{const target=event.target.closest('[data-graph-node-id]');if(target)highlight(target.dataset.graphNodeId);});
 root.addEventListener('focusout',()=>highlight(null));
 function activate(event){const target=event.target.closest('[data-graph-node-id]');if(!target)return;if(event.type==='keydown'&&!['Enter',' '].includes(event.key))return;if(event.type==='keydown')event.preventDefault();const node=byId.get(target.dataset.graphNodeId);if(node)window.openGraphConceptCard(node);}
 root.addEventListener('click',activate);root.addEventListener('keydown',activate);
 new ResizeObserver(refresh).observe(root);
 document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;}else refresh();});
 document.addEventListener('workspacechange',refresh);
 window.MathGraphRenderer={refresh,clear(){observer.disconnect();cancelAnimationFrame(frame);frame=0;svg=null;nodes=[];byId.clear();points.clear();adjacent.clear();ranked=[];},render(graph,colors){
  const started=performance.now();revision++;observer.disconnect();cancelAnimationFrame(frame);frame=0;focused=null;
  nodes=graph.nodes||[];byId=new Map(nodes.map(node=>[String(node.id),node]));points=new Map();adjacent=new Map(nodes.map(node=>[String(node.id),[]]));
  const edges=(graph.edges||[]).filter(e=>byId.has(String(e.source))&&byId.has(String(e.target)));
  edges.forEach(e=>{adjacent.get(String(e.source)).push(String(e.target));adjacent.get(String(e.target)).push(String(e.source));});
  ranked=[...nodes].sort((a,b)=>adjacent.get(String(b.id)).length-adjacent.get(String(a.id)).length||String(a.id).localeCompare(String(b.id)));
  const radius=Math.max(220,Math.sqrt(nodes.length)*23),width=Math.max(900,radius*2+160),height=Math.max(620,radius*2+160);base={width,height};
  ranked.forEach((node,index)=>{const r=nodes.length===1?0:radius*Math.sqrt((index+.5)/nodes.length),angle=index*2.399963229728653;points.set(String(node.id),{x:width/2+Math.cos(angle)*r,y:height/2+Math.sin(angle)*r});});
  svg=el('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':`数学知识图谱，${nodes.length}个节点，${edges.length}条关系；可展开缩放、点击或按回车查看知识点`,class:'fast-graph'});
  svg.append(el('rect',{width:'100%',height:'100%',fill:'#071525'}));
  const edgeGroup=el('g',{class:'fast-graph-edges','pointer-events':'none'}),batches=new Map();
  edges.forEach(edge=>{const a=points.get(String(edge.source)),b=points.get(String(edge.target)),type=byId.get(String(edge.source)).type||'concept';batches.set(type,(batches.get(type)||'')+`M${a.x.toFixed(1)} ${a.y.toFixed(1)}L${b.x.toFixed(1)} ${b.y.toFixed(1)}`);});
  batches.forEach((d,type)=>edgeGroup.append(el('path',{d,fill:'none',stroke:colors[type]||colors.concept,'stroke-opacity':.17,'stroke-width':.7,'vector-effect':'non-scaling-stroke'})));svg.append(edgeGroup);
  const nodeGroup=el('g',{class:'fast-graph-nodes'}),fragment=document.createDocumentFragment();
  nodes.forEach(node=>{const p=points.get(String(node.id)),group=el('g',{'data-graph-node-id':node.id,role:'button',tabindex:0,'aria-label':`查看知识点：${node.name}`,class:'fast-graph-node'});const title=el('title');title.textContent=node.name;
   group.append(el('circle',{cx:p.x,cy:p.y,r:nodes.length>100?7:11,fill:colors[node.type]||colors.concept,stroke:'#ccefff','stroke-opacity':.45,'stroke-width':.7}),el('circle',{cx:p.x,cy:p.y,r:15,fill:'transparent'}),title);fragment.append(group);
  });nodeGroup.append(fragment);svg.append(nodeGroup,el('g',{class:'fast-graph-labels','pointer-events':'none'}),el('g',{class:'fast-graph-focus','pointer-events':'none'}));root.replaceChildren(svg);
  observer.observe(svg,{attributes:true,attributeFilter:['viewBox']});drawLabels();
  root.dataset.renderMs=(performance.now()-started).toFixed(2);root.dataset.renderer='static-svg';root.dataset.revision=revision;
 },get stats(){return {nodes:nodes.length,edges:[...adjacent.values()].reduce((a,b)=>a+b.length,0)/2,labels:svg?.querySelector('.fast-graph-labels')?.childElementCount||0,renderMs:Number(root.dataset.renderMs||0),pendingFrame:Boolean(frame)};}};
})();
