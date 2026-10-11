"""Bounded local symbolic experiments. No Python eval or model-generated numbers."""
import ast
import math
import multiprocessing as mp
from itertools import combinations
from queue import Empty

import sympy as s
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix='/math-lab', tags=['Math experiments'])
X = s.Symbol('x', real=True)
FUNCTIONS = {name: getattr(s, name) for name in ('sin','cos','tan','cot','sec','csc','asin','acos','atan','sinh','cosh','tanh','exp','log','sqrt','Abs')}
FUNCTIONS['abs'] = s.Abs


def expression(text, domain_terms=None):
    if not text or len(text) > 180:
        raise ValueError('表达式长度须为 1–180 个字符')
    tree = ast.parse(text.replace('^', '**'), mode='eval')
    if len(list(ast.walk(tree))) > 64:
        raise ValueError('表达式过于复杂，请拆成小实验')
    def record(value):
        if domain_terms is not None:domain_terms.append(value)
        return value
    def visit(n):
        if isinstance(n, ast.Constant) and type(n.value) in (int,float) and math.isfinite(n.value) and abs(n.value) <= 10000:
            return s.Rational(str(n.value))
        if isinstance(n, ast.Name) and n.id in ('x','pi','e'):
            return {'x':X,'pi':s.pi,'e':s.E}[n.id]
        if isinstance(n, ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):
            a=visit(n.operand);return -a if isinstance(n.op,ast.USub) else a
        if isinstance(n,ast.BinOp):
            a,b=visit(n.left),visit(n.right)
            if isinstance(n.op,ast.Pow):
                if b.is_Rational:
                    if abs(b)>12 or b.q>12:raise ValueError('常数幂指数须为绝对值不超过 12 的有理数')
                elif not (a.is_number and a.is_positive and a<=100):raise ValueError('变量指数只用于不超过 100 的正数底数')
                record(s.Pow(a,b,evaluate=False))
                return a**b
            if isinstance(n.op,ast.Add):return a+b
            if isinstance(n.op,ast.Sub):return a-b
            if isinstance(n.op,ast.Mult):return a*b
            if isinstance(n.op,ast.Div):
                if b==0:raise ValueError('不能除以零')
                if b.has(s.sin,s.cos,s.tan,s.cot,s.sec,s.csc):
                    raise ValueError('三角函数倒数请用 sec、csc、cot 等独立函数表示')
                record(s.Pow(b,-1,evaluate=False))
                return a/b
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in FUNCTIONS and len(n.args)==1 and not n.keywords:
            return record(FUNCTIONS[n.func.id](visit(n.args[0])))
        raise ValueError('仅支持 x、pi、e、四则运算及列出的数学函数；乘法请写 *')
    return visit(tree.body)


def real_number(value):
    try:
        z=complex(s.N(value,16))
        return float(z.real) if abs(z.imag)<1e-12 and math.isfinite(z.real) else None
    except (TypeError,ValueError,OverflowError):return None


class CalculusInput(BaseModel):
    expression: str = Field(min_length=1,max_length=180)
    mode: str = 'derivative'
    x: float = Field(default=1,ge=-20,le=20)
    h: float = Field(default=.1,ge=-5,le=5)
    a: float = Field(default=0,ge=-20,le=20)
    b: float = Field(default=1,ge=-20,le=20)
    n: int = Field(default=30,ge=1,le=200)


def calculus(payload):
    domain_terms=[]
    f=expression(payload['expression'],domain_terms);mode=payload['mode']
    domain_terms=list(dict.fromkeys([f,*domain_terms]))
    if any(term.has(s.zoo,s.oo,-s.oo,s.nan,s.I) for term in domain_terms):raise ValueError('请使用有实数定义域的有限值函数')
    if mode not in ('derivative','integral'):raise ValueError('实验类型无效')
    # Periodic ImageSet complements are often undecidable via Set.contains.
    # For affine trig arguments enumerate poles numerically on bounded intervals,
    # retaining an exact symbolic domain for display. Other expressions use SymPy.
    periodic=[]
    for atom in set().union(*(term.atoms(s.tan,s.cot,s.sec,s.csc) for term in domain_terms)):
        argument=atom.args[0];slope=s.diff(argument,X);offset=argument.subs(X,0)
        if slope.has(X) or not slope.is_number or slope==0 or not offset.is_number:
            raise ValueError('含奇点的三角函数目前支持 a*x+b 形式的参数')
        periodic.append((atom,float(slope),float(offset),.5 if atom.func in (s.tan,s.sec) else 0))
    base_domain=s.S.Reals
    coefficients=[]
    placeholders={atom:s.Dummy(real=True) for atom,_,_,_ in periodic}
    for term in domain_terms:
        if periodic:
            regular=term.xreplace(placeholders)
            if not regular.is_polynomial(*placeholders.values()):
                raise ValueError('周期三角函数支持多项式组合；嵌套对数、根式或倒数请拆成独立实验')
            coefficients.extend(s.Poly(regular,*placeholders.values()).coeffs())
        else:coefficients.append(term)
    for coefficient in coefficients:
        base_domain=s.Intersection(base_domain,s.calculus.util.continuous_domain(coefficient,X,s.S.Reals))
    domain=base_domain
    k=s.Symbol('k',integer=True)
    for atom,_,_,shift in periodic:
        arg=atom.args[0];slope=s.diff(arg,X);offset=arg.subs(X,0)
        poles=s.ImageSet(s.Lambda(k,(s.pi*(k+s.Rational(str(shift)))-offset)/slope),s.S.Integers)
        domain=s.Complement(domain,poles)
    def contains(point):
        if base_domain.contains(point)!=s.true:return False
        for _,slope,offset,shift in periodic:
            phase=(slope*float(point)+offset)/math.pi-shift
            if abs(phase-round(phase))<1e-12:return False
        return True
    def interval_ok(a,b):
        if s.Interval(min(a,b),max(a,b)).is_subset(base_domain)!=True:return False
        for _,slope,offset,shift in periodic:
            ends=sorted(((slope*float(a)+offset)/math.pi-shift,(slope*float(b)+offset)/math.pi-shift))
            if math.ceil(ends[0]-1e-12)<=math.floor(ends[1]+1e-12):return False
        return True
    d=s.diff(f,X)
    if f.func in (s.tan,s.cot,s.sec,s.csc):
        u=f.args[0];scale=s.diff(u,X)
        primitives={s.tan:-s.log(s.Abs(s.cos(u))),s.cot:s.log(s.Abs(s.sin(u))),
                    s.sec:s.log(s.Abs(s.sec(u)+s.tan(u))),s.csc:-s.log(s.Abs(s.csc(u)+s.cot(u)))}
        F=primitives[f.func]/scale
    else:F=s.integrate(f,X)
    xmin=min(-6,payload['a'],payload['b'],payload['x']-1);xmax=max(6,payload['a'],payload['b'],payload['x']+payload['h']+1)
    samples=[]
    for i in range(481):
        x=xmin+(xmax-xmin)*i/480
        samples.append([x,real_number(f.subs(X,x)) if contains(s.Rational(str(x))) else None])
    result={'function':s.latex(f),'derivative':s.latex(d),'primitive':s.latex(F) if not F.has(s.Integral) else None,'domain':s.latex(domain),'samples':samples,'x_min':xmin,'x_max':xmax,'engine':'SymPy '+s.__version__}
    if mode=='derivative':
        x=s.Rational(str(payload['x']));h=s.Rational(str(payload['h']))
        if h==0:raise ValueError('增量 h 不能为零')
        if not contains(x) or not contains(x+h):raise ValueError('切点或割线端点不在实数定义域内')
        if real_number(f.subs(X,x)) is None or real_number(f.subs(X,x+h)) is None:
            raise ValueError('切点或割线端点没有有限实数函数值')
        t=s.Symbol('t',real=True)
        q=(f.subs(X,x+t)-f.subs(X,x))/t
        left=s.limit(q,t,0,dir='-');right=s.limit(q,t,0,dir='+')
        # At a domain endpoint a one-sided slope is not a two-sided derivative.
        interior=base_domain.interior.contains(x)==s.true and contains(x)
        tangent=real_number(right) if interior and s.simplify(left-right)==0 else None
        result.update(y=real_number(f.subs(X,x)),end=real_number(f.subs(X,x+h)),secant=real_number(q.subs(t,h)),tangent=tangent,left=s.latex(left),right=s.latex(right))
    else:
        a=s.Rational(str(payload['a']));b=s.Rational(str(payload['b']))
        if not interval_ok(a,b):
            raise ValueError('区间跨越未定义点或奇点；请选连续区间。此实验不把反常积分当作普通定积分')
        exact=s.simplify(F.subs(X,b)-F.subs(X,a)) if f.func in (s.tan,s.cot,s.sec,s.csc) else s.integrate(f,(X,a,b));dx=(float(b)-float(a))/payload['n'];rectangles=[];total=0
        for i in range(payload['n']):
            pos=float(a)+i*dx;y=real_number(f.subs(X,pos+dx/2))
            if y is None:raise ValueError('区间内函数值不可计算')
            total+=y*dx;rectangles.append({'x':pos,'dx':dx,'y':y})
        result.update(exact=s.latex(exact) if not exact.has(s.Integral) else None,exact_value=real_number(exact),sum=total,rectangles=rectangles)
    return result


class MatrixInput(BaseModel):
    matrix: list[list[str]]


def matrix_analysis(payload):
    rows=payload['matrix'];n=len(rows)
    if not 1<=n<=4 or any(len(row)!=n for row in rows):raise ValueError('输入 1–4 阶方阵，每行元素数须相同')
    import re
    def rational(text):
        if len(text)>24 or not re.fullmatch(r'[+-]?(?:\d{1,6}(?:\.\d{1,6})?|\d{1,6}/\d{1,6})',text.strip()):raise ValueError('矩阵元素仅支持整数、小数或分数，如 -2、0.5、1/3')
        q=s.Rational(text)
        if abs(q)>10000:raise ValueError('矩阵元素绝对值不得超过 10000')
        return q
    A=s.Matrix([[rational(v) for v in row] for row in rows]);lam=s.Symbol('lambda');char=A.charpoly(lam).as_expr();det=A.det();rank=A.rank()
    principal=[]
    for k in range(1,n+1):
        for ids in combinations(range(n),k):principal.append({'order':k,'indices':[i+1 for i in ids],'value':str(A.extract(ids,ids).det())})
    # First linear dependence among I,A,... gives the monic minimal polynomial.
    columns=[];power=s.eye(n);minimal=None
    for k in range(n+1):
        vector=s.Matrix(list(power));B=s.Matrix.hstack(*columns) if columns else None
        if B is not None and B.rank()==B.row_join(vector).rank():
            coeff=B.gauss_jordan_solve(vector)[0];minimal=lam**k-sum(coeff[i]*lam**i for i in range(k));break
        columns.append(vector);power=power*A
    eigen=[];directions=[]
    eigen_data=A.eigenvects()
    for val,mult,basis in eigen_data:
        numeric=complex(s.N(val,12))
        eigen.append({'value':str(val),'latex':s.latex(val),'real':numeric.real,'imag':numeric.imag,'algebraic_multiplicity':mult,'geometric_multiplicity':len(basis),'vectors':[[str(q) for q in v] for v in basis]})
        if n==2 and val.is_real:
            for v in basis:directions.append({'value':float(s.N(val)),'vector':[float(s.N(q)) for q in v]})
    diagonal_C=sum(e['geometric_multiplicity'] for e in eigen)==n
    symmetric=A==A.T;leading=[str(A[:k,:k].det()) for k in range(1,n+1)]
    checks={'trace_equals_eigen_sum':s.simplify(sum(val*mult for val,mult,_ in eigen_data)-A.trace())==0,'det_equals_eigen_product':s.simplify(s.prod(val**mult for val,mult,_ in eigen_data)-det)==0,'cayley_hamilton':sum((coef*(A**(n-i)) for i,coef in enumerate(A.charpoly().all_coeffs())),s.zeros(n))==s.zeros(n)}
    positive=all(s.Rational(v)>0 for v in leading) if symmetric else None
    semipositive=all(s.Rational(p['value'])>=0 for p in principal) if symmetric else None
    return {'matrix':[[str(q) for q in A.row(i)] for i in range(n)],'size':n,'determinant':str(det),'trace':str(A.trace()),'rank':rank,'nullity':n-rank,'characteristic':s.latex(char),'minimal':s.latex(minimal),'rref':[[str(q) for q in A.rref()[0].row(i)] for i in range(n)],'inverse':[[str(q) for q in A.inv().row(i)] for i in range(n)] if det else None,'nullspace':[[str(q) for q in v] for v in A.nullspace()],'eigenvalues':eigen,'directions':directions,'principal_minors':principal,'leading_minors':leading,'symmetric':symmetric,'positive_definite':positive,'positive_semidefinite':semipositive,'diagonalizable_complex':diagonal_C,'diagonalizable_real':diagonal_C and all(val.is_real is True for val,_,_ in eigen_data),'checks':checks,'engine':'SymPy '+s.__version__}


def worker(kind,payload,queue):
    try:queue.put({'result':calculus(payload) if kind=='calculus' else matrix_analysis(payload)})
    except Exception as exc:queue.put({'error':str(exc) or '该对象目前无法计算'})


def bounded(kind,payload):
    ctx=mp.get_context('spawn');q=ctx.Queue();p=ctx.Process(target=worker,args=(kind,payload,q));p.start()
    try:
        value=q.get(timeout=12)
        if 'error' in value:raise HTTPException(400,detail=value['error'])
        return value['result']
    except Empty:raise HTTPException(408,detail='符号计算超过 12 秒，请简化表达式或矩阵')
    finally:
        if p.is_alive():p.terminate()
        p.join(timeout=1);q.close()


@router.post('/calculus')
def calculate(request:CalculusInput):return bounded('calculus',request.model_dump())


@router.post('/matrix')
def analyze(request:MatrixInput):return bounded('matrix',request.model_dump())
