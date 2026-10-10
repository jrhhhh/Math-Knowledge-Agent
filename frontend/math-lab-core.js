/* Fixed examples only: no evaluation of user expressions. */
(function (root) {
  const examples = {
    square:{label:'x²',f:x=>x*x,d:x=>2*x,F:x=>x*x*x/3,condition:'多项式在实数域上连续且可导。'},
    cube:{label:'x³',f:x=>x*x*x,d:x=>3*x*x,F:x=>x**4/4,condition:'多项式在实数域上连续且可导。'},
    sine:{label:'sin x',f:Math.sin,d:Math.cos,F:x=>-Math.cos(x),condition:'x 以弧度计；sin x 在实数域上连续且可导。'},
    absolute:{label:'|x|',f:Math.abs,d:x=>x===0?null:Math.sign(x),F:x=>x*Math.abs(x)/2,condition:'|x| 连续；x=0 处左导数 −1、右导数 1，因此不可导。'},
  };
  function derivative(key,x,h) {
    if(!examples[key] || !Number.isFinite(x) || !Number.isFinite(h) || h===0)throw Error('参数无效');
    const e=examples[key];return {y:e.f(x),end:e.f(x+h),secant:(e.f(x+h)-e.f(x))/h,tangent:e.d(x)};
  }
  function integral(key,a,b,n) {
    if(!examples[key] || ![a,b,n].every(Number.isFinite) || !Number.isInteger(n) || n<1 || n>200)throw Error('参数无效');
    const e=examples[key],dx=(b-a)/n;let sum=0;
    const rectangles=Array.from({length:n},(_,i)=>{const x=a+i*dx,y=e.f(x+dx/2);sum+=y*dx;return {x,dx,y};});
    return {exact:e.F(b)-e.F(a),sum,rectangles};
  }
  function transform(m,v) {if(m.length!==4 || v.length!==2 || ![...m,...v].every(Number.isFinite))throw Error('参数无效');return [m[0]*v[0]+m[1]*v[1],m[2]*v[0]+m[3]*v[1]];}
  const api={examples,derivative,integral,transform,determinant:m=>m[0]*m[3]-m[1]*m[2]};
  if(typeof module==='object' && module.exports)module.exports=api;else root.MathLabCore=api;
})(typeof window==='object'?window:this);
