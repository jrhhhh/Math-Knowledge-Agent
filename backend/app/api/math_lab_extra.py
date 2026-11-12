"""Finite series explorations and bounded real-valued surface sampling."""
import math
from typing import Literal

import sympy as s
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.api.math_lab import X, expression, real_number, bounded

router = APIRouter(prefix='/math-lab', tags=['Math experiments'])
Y = s.Symbol('y', real=True)


class SeriesInput(BaseModel):
    kind: Literal['geometric', 'p', 'alternating', 'exp', 'custom'] = 'geometric'
    n: int = Field(default=40, ge=1, le=300)
    expression: str = Field(default='1/n^2', min_length=1, max_length=180)
    parameter: float = Field(default=.5, ge=-10, le=10, allow_inf_nan=False)


def series(payload):
    count, parameter, kind = payload['n'], payload['parameter'], payload['kind']
    n = s.Symbol('n', integer=True, positive=True)
    exact_parameter = s.Rational(str(parameter))
    if kind == 'custom':
        constraints = []
        term = expression(payload.get('expression','1/n^2'), constraints, {'n':n, 'p':exact_parameter})
        values = []
        for index in range(1,count+1):
            evaluated = [real_number(part.subs(n,index)) for part in [term,*constraints]]
            if any(value is None for value in evaluated):
                raise ValueError(f'第 {index} 项没有有限实数值，请检查通项的定义域或数值是否过大')
            values.append(evaluated[0])
        converges, limit = None, None
        conclusion = '自定义级数：仅计算所选前 N 项，尚未判定收敛性；部分和看似稳定不构成证明'
    elif kind == 'geometric':
        term = exact_parameter**(n-1)
        values = [parameter**k for k in range(count)]
        converges = abs(parameter) < 1
        limit = 1/(1-parameter) if converges else None
        conclusion = '绝对收敛，|r|<1' if converges else '发散，|r|≥1，通项不趋于0'
    elif kind in ('p', 'alternating'):
        if parameter <= 0: raise ValueError('p须大于0')
        term = 1/n**exact_parameter
        values = [1/(k**parameter) for k in range(1,count+1)]
        if kind == 'alternating':
            term = (-1)**(n+1)*term
            values = [value*(-1)**k for k,value in enumerate(values)]
            converges = True
            limit = real_number(s.dirichlet_eta(exact_parameter))
            conclusion = '绝对收敛，p>1' if parameter>1 else '条件收敛，0<p≤1；余项绝对值不超过下一项'
        else:
            converges = parameter > 1
            limit = real_number(s.zeta(exact_parameter)) if converges else None
            conclusion = '收敛，p>1' if converges else '发散，0<p≤1；通项趋于0仍不足以保证收敛'
    else:
        term = exact_parameter**(n-1)/s.factorial(n-1)
        values = [1.0]
        for k in range(1,count): values.append(values[-1]*parameter/k)
        converges, limit = True, math.exp(parameter)
        conclusion = '对每个实数x都绝对收敛，和为eˣ'
    sums, total = [], 0.0
    for value in values:
        try: total = math.fsum([total, value])
        except OverflowError: raise ValueError('部分和超出浮点数范围，请减少项数或调整通项')
        if not math.isfinite(total): raise ValueError('部分和超出浮点数范围，请减少项数或调整通项')
        sums.append(total)
    return {'terms':values,'partial_sums':sums,'term_latex':s.latex(term),
            'limit':limit,'converges':converges,'conclusion':conclusion,
            'error':abs(total-limit) if limit is not None else None,
            'remainder_bound':1/((count+1)**parameter) if kind=='alternating' else None,
            'engine':'安全通项解析 + 有限项浮点计算' if kind=='custom' else '标准级数判别 + 有限项浮点计算'}


class SurfaceInput(BaseModel):
    expression: str = Field(default='x^2+y^2', min_length=1, max_length=180)
    radius: float = Field(default=3, ge=.2, le=100, allow_inf_nan=False)
    x: float = Field(default=1, ge=-100, le=100, allow_inf_nan=False)
    y: float = Field(default=1, ge=-100, le=100, allow_inf_nan=False)
    a: float = Field(default=1, ge=-100, le=100, allow_inf_nan=False)
    b: float = Field(default=1, ge=-100, le=100, allow_inf_nan=False)
    resolution: int = Field(default=31, ge=15, le=41)


def surface(payload):
    constraints = []
    f = expression(payload['expression'], constraints, {'x':X, 'y':Y, 'a':s.Rational(str(payload.get('a',1))), 'b':s.Rational(str(payload.get('b',1)))})
    if f.has(s.zoo,s.oo,-s.oo,s.nan,s.I): raise ValueError('请使用具有实数定义域的有限值函数')
    terms = list(dict.fromkeys([f,*constraints]))
    evaluators = [s.lambdify((X,Y),term,modules='math',cse=True) for term in terms]
    def value(x,y):
        try:
            outputs = [complex(evaluate(x,y)) for evaluate in evaluators]
            if any(abs(v.imag)>1e-12 or not math.isfinite(v.real) for v in outputs): return None
            return float(outputs[0].real)
        except (ValueError,ZeroDivisionError,OverflowError,TypeError): return None
    count, radius = payload['resolution'],payload['radius']
    axis = [-radius+2*radius*i/(count-1) for i in range(count)]
    grid = [[value(x,y) for x in axis] for y in axis]
    finite = [v for row in grid for v in row if v is not None]
    if not finite: raise ValueError('所选区域没有可绘制的实数采样值，请调整表达式或范围')
    x,y = payload['x'],payload['y']
    z = value(x,y)
    dx,dy = None,None
    if z is not None:
        # Check both one-sided difference quotients, including nonsmooth examples.
        for variable, fixed, point, which in [(X,{Y:s.Rational(str(y))},s.Rational(str(x)),'x'),(Y,{X:s.Rational(str(x))},s.Rational(str(y)),'y')]:
            section = f.subs(fixed)
            base = section.subs(variable,point)
            quotient = (section-base)/(variable-point)
            try:
                left,right = s.limit(quotient,variable,point,dir='-'),s.limit(quotient,variable,point,dir='+')
                derivative = real_number(right) if left==right else None
            except (NotImplementedError, ValueError, TypeError):
                derivative = None
            # A missing original-domain side cannot establish a two-sided partial derivative.
            for delta in (1e-5,-1e-5):
                neighbor = value(x+delta,y) if which=='x' else value(x,y+delta)
                if neighbor is None:
                    derivative = None
            if which=='x': dx=derivative
            else: dy=derivative
    return {'axis':axis,'grid':grid,'z_min':min(finite),'z_max':max(finite),
            'valid_points':len(finite),'total_points':count*count,
            'function':s.latex(f),'dx_latex':s.latex(s.diff(f,X)), 'dy_latex':s.latex(s.diff(f,Y)),
            'point':{'x':x,'y':y,'z':z,'dx':dx,'dy':dy},
            'engine':'SymPy '+s.__version__+' + 实数网格采样'}


@router.post('/series')
def calculate_series(request:SeriesInput): return bounded('series',request.model_dump())


@router.post('/surface')
def calculate_surface(request:SurfaceInput): return bounded('surface',request.model_dump())
