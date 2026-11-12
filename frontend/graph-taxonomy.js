/* Navigation taxonomy only. Never creates prerequisite edges or changes concepts. */
(function(root){
 const subjects=[['数学分析',/分析|微积分|实数|函数|极坐标|不尽根/],['高等代数',/代数|矩阵|向量/],['拓扑与几何',/拓扑|几何|图像/],['数论',/数论/],['证明与逻辑',/证明|逻辑/],['计算与应用',/量子|计算|优化|概率|统计|应用/]];
 const topics=[
 ['实数与数系',/实数|有理|无理|不尽根|数系|数轴|戴德金|dedekind/i],
 ['测度与可测性',/测度|可测|勒贝格|lebesgue|lusin|叶戈罗夫|egorov/i],
 ['数列与极限',/数列|极限|柯西|上确界|下确界|limit|sequence/i],
 ['级数与函数列',/级数|函数列|一致收敛|幂级数|series|convergence/i],
 ['积分与面积',/积分|原函数|面积|integral|primitive/i],
 ['微分与导数',/导数|微分|中值定理|泰勒|taylor|derivative/i],
 ['多元函数',/多元|二元|偏导|方向导数|梯度|重积分|偏微分/],
 ['函数与连续性',/函数|连续|映射|function|continu/i],
 ['紧性与拓扑结构',/紧|拓扑|开集|闭集|覆盖|度量|邻域/],
 ['矩阵与线性空间',/矩阵|向量|特征|线性|行列式|二次型|matrix|linear/i],
 ['方程与多项式',/方程|多项式|二项式|根式|因式/],
 ['几何与坐标',/几何|坐标|曲线|直线|圆锥|圆|椭圆|抛物|双曲/],
 ['证明方法',/证明|反证|归纳|逆反|构造|不等式/],
 ['计算方法',/量子|算法|计算|优化/]
 ];
 function partition(nodes,labelOf){const map=new Map();nodes.forEach(node=>{const label=labelOf(node);if(!map.has(label))map.set(label,[]);map.get(label).push(node);});return [...map].map(([name,nodes])=>({name,nodes})).sort((a,b)=>b.nodes.length-a.nodes.length||a.name.localeCompare(b.name));}
 function subject(node){const field=String(node.field||'');return subjects.find(([,pattern])=>pattern.test(field))?.[0]||'其他知识';}
 function topic(node){const text=String(node.name||'')+' '+String(node.description||'').slice(0,160);return topics.find(([,pattern])=>pattern.test(text))?.[0]||'其他主题';}
 function children(group,level){
  if(level===0)return partition(group.nodes,subject);
  if(level===1){const groups=partition(group.nodes,topic);if(groups.length>1)return groups;}
  if(group.nodes.length<=36)return [];
  if(level===2){const types={concept:'概念与定义',theorem:'定理与命题',property:'性质与结论',method:'方法与证明'};const groups=partition(group.nodes,n=>types[n.type]||'其他知识点');if(groups.length>1)return groups;}
  const sorted=[...group.nodes].sort((a,b)=>String(a.name).localeCompare(String(b.name),'zh-CN'));
  return Array.from({length:Math.ceil(sorted.length/36)},(_,i)=>({name:`知识点 ${i*36+1}–${Math.min(sorted.length,(i+1)*36)}`,nodes:sorted.slice(i*36,(i+1)*36)}));
 }
 const api={subject,topic,partition,children};if(typeof module==='object'&&module.exports)module.exports=api;else root.MathGraphTaxonomy=api;
})(typeof window==='object'?window:this);
