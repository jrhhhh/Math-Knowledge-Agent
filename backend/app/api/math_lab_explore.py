"""Additional teaching experiments; exact algebra and explicitly sampled graphics."""
import math
import re
from typing import Literal

import numpy as np
import sympy as s
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.api.math_lab import X, expression, real_number, bounded
from app.api.math_lab_extra import Y, surface

router = APIRouter(prefix='/math-lab', tags=['Math experiments'])


class ExploreInput(BaseModel):
    kind: Literal['taylor','sequence','path','gradient','system','quadratic','decomposition']
    expression: str = Field(default='sin(x)', min_length=1, max_length=180)
    limit_expression: str = Field(default='0', min_length=1, max_length=180)
    path_x: str = Field(default='t', min_length=1, max_length=180)
    path_y: str = Field(default='t^2', min_length=1, max_length=180)
    left: float = Field(default=-3, ge=-100, le=100, allow_inf_nan=False)
    right: float = Field(default=3, ge=-100, le=100, allow_inf_nan=False)
    center: float = Field(default=0, ge=-20, le=20, allow_inf_nan=False)
    order: int = Field(default=4, ge=0, le=12)
    index: int = Field(default=10, ge=1, le=300)
    epsilon: float = Field(default=.1, gt=0, le=10, allow_inf_nan=False)
    x: float = Field(default=1, ge=-100, le=100, allow_inf_nan=False)
    y: float = Field(default=1, ge=-100, le=100, allow_inf_nan=False)
    radius: float = Field(default=3, ge=.2, le=100, allow_inf_nan=False)
    angle: float = Field(default=30, ge=-180, le=180, allow_inf_nan=False)
    matrix: list[list[str]] = Field(default_factory=lambda:[['2','1'],['1','2']])
    rhs: list[str] = Field(default_factory=lambda:['1','2'])
    vector: list[float] = Field(default_factory=lambda:[1,1], min_length=2, max_length=2)
    iterations: int = Field(default=8, ge=1, le=40)


def sampler(text, variables, max_power=12):
    constraints=[]
    f=expression(text,constraints,variables,max_power=max_power)
    funcs=[s.lambdify(tuple(dict.fromkeys(v for v in variables.values() if isinstance(v,s.Symbol))),part,modules='math',cse=True) for part in [f,*constraints]]
    def evaluate(*args):
        try:
            vals=[complex(fn(*args)) for fn in funcs]
            if any(not math.isfinite(v.real) or abs(v.imag)>1e-12 for v in vals):return None
            return float(vals[0].real)
        except (ValueError,TypeError,OverflowError,ZeroDivisionError):return None
    return f,evaluate


def curve_samples(fn,left,right,count=301):
    if left>=right:raise ValueError('绘图区间左端必须小于右端')
    return [[left+(right-left)*i/(count-1),fn(left+(right-left)*i/(count-1))] for i in range(count)]


def taylor(p):
    f,evaluate=sampler(p['expression'],{'x':X})
    c=s.Rational(str(p['center']))
    if evaluate(float(c)) is None:raise ValueError('展开点不在函数的有限实数定义域内')
    domain=s.calculus.util.continuous_domain(f,X,s.S.Reals)
    if domain.interior.contains(c)!=s.true:raise ValueError('Taylor 展开点须在实数定义域内部')
    poly=0
    for k in range(p['order']+1):
        derivative=s.diff(f,X,k)
        coeff=derivative.subs(X,c)
        # A finite value alone does not establish existence of the derivative (e.g. |x| at 0).
        if real_number(coeff) is None or coeff.has(s.Derivative,s.Subs):raise ValueError('此阶导数在展开点不存在或无法确定，请换点或降低阶数')
        if k>0:
            prev=s.diff(f,X,k-1)
            q=(prev-prev.subs(X,c))/(X-c)
            lo,hi=s.limit(q,X,c,dir='-'),s.limit(q,X,c,dir='+')
            if real_number(lo) is None or s.simplify(lo-hi)!=0 or s.simplify(hi-coeff)!=0:
                raise ValueError(f'展开点的第 {k} 阶双侧导数不存在或无法确定')
        poly+=coeff*(X-c)**k/s.factorial(k)
    _,approx=sampler(str(poly),{'x':X})
    samples=curve_samples(evaluate,p['left'],p['right'])
    approximation=curve_samples(approx,p['left'],p['right'])
    errors=[[x,None if y is None or approximation[i][1] is None else abs(y-approximation[i][1])] for i,(x,y) in enumerate(samples)]
    finite=[e for _,e in errors if e is not None and math.isfinite(e)]
    if not finite:raise ValueError('当前区间没有可比较的有限实数值')
    return {'curves':[{'label':'原函数','points':samples},{'label':'Taylor 多项式','points':approximation}],
            'error_curve':errors,'max_sample_error':max(finite),'polynomial':s.latex(poly),
            'note':'最大误差仅针对绘图采样点；不是严格误差上界，也未判定 Taylor 级数的收敛范围。'}


def sequence(p):
    n=s.Symbol('n',integer=True,positive=True)
    # Substitute the selected integer before safe power validation (allows x^n).
    f,evaluate=sampler(p['expression'],{'x':X,'n':s.Integer(p['index'])},max_power=300)
    limit,limit_value=sampler(p['limit_expression'],{'x':X})
    samples=curve_samples(evaluate,p['left'],p['right'])
    reference=curve_samples(limit_value,p['left'],p['right'])
    errors=[[x,None if y is None or reference[i][1] is None else abs(y-reference[i][1])] for i,(x,y) in enumerate(samples)]
    finite=[e for _,e in errors if e is not None and math.isfinite(e)]
    if not finite:raise ValueError('当前区间没有可比较的有限实数值')
    return {'curves':[{'label':f'f{p["index"]}(x)','points':samples},{'label':'候选极限函数','points':reference}],
            'epsilon':p['epsilon'],'error_curve':errors,'max_sample_error':max(finite),
            'within_band':len(finite)==len(samples) and max(finite)<=p['epsilon'],
            'function':s.latex(f),'reference':s.latex(limit),
            'note':'极限函数由你提供，尚未验证。采样点全部进入 ε 带不构成一致收敛证明；这里只检查当前 n，网格可能遗漏尖峰。'}


def path(p):
    t=s.Symbol('t',real=True)
    f,evaluate=sampler(p['expression'],{'x':X,'y':Y})
    px,fx=sampler(p['path_x'],{'t':t});py,fy=sampler(p['path_y'],{'t':t})
    if any(s.limit(q,t,0,dir=side)!=0 for q in [px,py] for side in ['-','+']):
        raise ValueError('路径 x(t)、y(t) 必须在 t→0 的左右两侧都趋于0')
    points=[];table=[]
    for k in range(1,81):
        exponent=k/10;v=10**(-exponent);x,y=fx(v),fy(v)
        z=evaluate(x,y) if x is not None and y is not None and (x!=0 or y!=0) else None
        points.append([exponent,z])
        if k%10==0:table.append({'t':v,'x':x,'y':y,'value':z})
    if not any(z is not None for _,z in points):raise ValueError('所选路径上没有可计算的有限实数值')
    substitution=f.subs({X:px,Y:py},simultaneous=True)
    limits=[]
    for side in ['-','+']:
        sign=-1 if side=='-' else 1
        side_valid=True
        for k in range(2,9):
            a,b=fx(sign*10**(-k)),fy(sign*10**(-k))
            if a is None or b is None or (a==0 and b==0) or evaluate(a,b) is None:side_valid=False;break
        if not side_valid:
            limits.append('该侧缺少有效实数采样，未确认');continue
        try:limits.append(s.latex(s.limit(substitution,t,0,dir=side)))
        except (ValueError,NotImplementedError):limits.append('未确定')
    return {'curves':[{'label':'沿路径的函数值（t>0）','points':points}], 'table':table,
            'path':s.latex(s.Tuple(px,py)), 'left_limit':limits[0],'right_limit':limits[1],
            'note':'横轴为 −log₁₀(t)，向右表示 t→0⁺。列出的极限仅对应此路径；不同路径极限不等可否定二元极限，路径极限相同不能证明二元极限存在。'}


def gradient(p):
    data=surface({**p,'a':1,'b':1,'resolution':31})
    point=data['point'];angle=math.radians(p['angle'])
    dx,dy=point['dx'],point['dy']
    data['direction']=[math.cos(angle),math.sin(angle)]
    data['directional_candidate']=dx*math.cos(angle)+dy*math.sin(angle) if dx is not None and dy is not None else None
    data['note']='箭头表示偏导数组成的向量。只有函数在该点可微时，方向导数才等于梯度与单位方向的内积；本实验没有自动证明可微性。线性平面同样以可微为条件。'
    return data


def rational_matrix(rows):
    if not 1<=len(rows)<=4 or not 1<=len(rows[0])<=4 or any(len(row)!=len(rows[0]) for row in rows):
        raise ValueError('矩阵须为1–4行、1–4列，每行列数相同')
    def parse(v):
        if len(v)>24 or not re.fullmatch(r'[+-]?(?:\d{1,6}(?:\.\d{1,6})?|\d{1,6}/\d{1,6})',v.strip()):raise ValueError('矩阵与向量元素须为整数、小数或分数')
        try:q=s.Rational(v)
        except (ValueError,ZeroDivisionError):raise ValueError('分数的分母不能为零，元素须为有效数值')
        if not q.is_finite or abs(q)>10000:raise ValueError('元素须有限且绝对值不超过10000')
        return q
    return s.Matrix([[parse(v) for v in row] for row in rows])


def strings(matrix):return [[str(v) for v in row] for row in matrix.tolist()]


def system(p):
    A=rational_matrix(p['matrix'])
    if len(p['rhs'])!=A.rows:raise ValueError('b 的元素数须等于 A 的行数')
    b=rational_matrix([[v] for v in p['rhs']]);M=A.row_join(b)
    steps=[{'label':'初始增广矩阵 [A | b]','matrix':strings(M)}];row=0
    for col in range(A.cols):
        pivot=next((i for i in range(row,A.rows) if M[i,col]!=0),None)
        if pivot is None:continue
        if pivot!=row:
            M.row_swap(row,pivot);steps.append({'label':f'交换 R{row+1} 与 R{pivot+1}','matrix':strings(M)})
        divisor=M[row,col]
        if divisor!=1:
            M.row_op(row,lambda v,j:v/divisor);steps.append({'label':f'R{row+1} ÷ ({divisor})','matrix':strings(M)})
        for other in range(A.rows):
            factor=M[other,col]
            if other!=row and factor!=0:
                M.row_op(other,lambda v,j:v-factor*M[row,j]);steps.append({'label':f'R{other+1} − ({factor}) R{row+1}','matrix':strings(M)})
        row+=1
        if row==A.rows:break
    rank,aug=A.rank(),M.rank();status='无解' if rank<aug else '唯一解' if rank==A.cols else '无穷多解'
    solution=None if rank<aug else s.latex(s.linsolve((A,b)))
    return {'steps':steps,'rank':rank,'augmented_rank':aug,'free_variables':None if rank<aug else A.cols-rank,
            'status':status,'solution':solution,'A':[[float(v) for v in r] for r in A.tolist()], 'b':[float(v) for v in b],
            'note':'行变换和解集使用精确有理数计算。图像仅显示二元方程的直线；一般方程组通过增广矩阵和解集查看。'}


def quadratic(p):
    A=rational_matrix(p['matrix'])
    if A.shape!=(2,2) or A!=A.T:raise ValueError('二次型实验请输入2×2实对称矩阵')
    values,Q=np.linalg.eigh(np.array(A,dtype=float))
    f=(s.Matrix([X,Y]).T*A*s.Matrix([X,Y]))[0]
    data=surface({**p,'expression':str(f),'a':1,'b':1,'resolution':31})
    data.update(eigenvalues=values.tolist(),orthogonal=Q.tolist(),form=s.latex(f),
                classification='正定' if A.is_positive_definite else '负定' if (-A).is_positive_definite else '半正定' if A.is_positive_semidefinite else '半负定' if (-A).is_positive_semidefinite else '不定',
                note='对称矩阵使用正交变换 x=Qu，化为 λ₁u₁²+λ₂u₂²。曲面和特征方向采用浮点数；正负定分类使用精确有理数矩阵。')
    return data


def decomposition(p):
    A=rational_matrix(p['matrix'])
    if A.shape!=(2,2):raise ValueError('分解与迭代实验请输入2×2矩阵')
    m=np.array(A,dtype=float);U,sv,Vt=np.linalg.svd(m)
    vector=np.array(p['vector'],dtype=float)
    if not np.isfinite(vector).all() or np.max(np.abs(vector))>10000:raise ValueError('初始向量须有限且绝对值不超过10000')
    trajectory=[vector.tolist()]
    for _ in range(p['iterations']):
        vector=m@vector
        if not np.isfinite(vector).all():raise ValueError('迭代数值溢出，请减少次数')
        trajectory.append(vector.tolist())
    return {'U':U.tolist(),'singular_values':sv.tolist(),'Vt':Vt.tolist(),'A':m.tolist(),'trajectory':trajectory,
            'spectral_radius':float(max(abs(v) for v in np.linalg.eigvals(m))),
            'residual':float(np.linalg.norm(U@np.diag(sv)@Vt-m)),
            'note':'SVD 分步展示 Vᵀ、Σ、U 对单位圆的作用；正交因子可能包含反射。迭代图显示 Aᵏv，有限步轨迹不构成收敛证明。'}


def explore(p):
    result=globals()[p['kind']](p)
    return {**result,'kind':p['kind'],'engine':'SymPy 精确/符号计算 + NumPy 与有限网格近似'}


@router.post('/explore')
def calculate(request:ExploreInput):return bounded('explore',request.model_dump())
