const assert=require('node:assert/strict');const T=require('../graph-taxonomy.js');
const nodes=Array.from({length:1060},(_,i)=>({id:i+1,name:i%2?'一致收敛与积分':'矩阵的特征值',field:i%3?'数学分析':'高等代数',type:'concept'}));
const root={name:'root',nodes},groups=T.children(root,0);
assert.equal(groups.reduce((n,g)=>n+g.nodes.length,0),1060);
assert.equal(new Set(groups.flatMap(g=>g.nodes.map(n=>n.id))).size,1060);
function leaves(group,depth){const children=T.children(group,depth);if(!children.length){assert(group.nodes.length<=36);return group.nodes;}assert(depth<8);return children.flatMap(child=>leaves(child,depth+1));}
const all=leaves(root,0);assert.equal(all.length,1060);assert.equal(new Set(all.map(n=>n.id)).size,1060);
assert.equal(T.subject({field:'实分析'}),'数学分析');assert.equal(T.subject({field:'拓扑学'}),'拓扑与几何');assert.equal(T.subject({field:'陌生领域'}),'其他知识');
assert.deepEqual(T.children({nodes:[]},0),[]);
console.log('Hierarchy partitions preserve every node and terminate in bounded leaves.');
