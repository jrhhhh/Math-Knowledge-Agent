"""Bounded exact polynomial calculus for one real variable.

The parser accepts only a small polynomial AST and rational interval bounds;
it never evaluates Python code or claims to prove facts outside that scope.
"""
from __future__ import annotations

import ast
from fractions import Fraction
import re

from app.ai.exact_math import ExactMathError

MAX_EXPRESSION_LENGTH = 240
MAX_DEGREE = 12
MAX_TERMS = 32
MAX_COEFFICIENT_BITS = 256

Polynomial = dict[int, Fraction]


def _provenance(operation: str, inputs: dict) -> dict:
    return {"tool_name": "bounded_polynomial", "tool_version": "1.0.0", "operation": operation,
            "input": inputs, "resource_limits": {"max_expression_length": MAX_EXPRESSION_LENGTH,
            "max_degree": MAX_DEGREE, "max_ast_nodes": 128, "max_terms": MAX_TERMS,
            "max_coefficient_bits": MAX_COEFFICIENT_BITS}}


def _check_coefficient(value: Fraction) -> Fraction:
    if value.numerator.bit_length() > MAX_COEFFICIENT_BITS or value.denominator.bit_length() > MAX_COEFFICIENT_BITS:
        raise ExactMathError("有理数系数超出允许范围。")
    return value


def _clean(poly: Polynomial) -> Polynomial:
    result = {degree: _check_coefficient(value) for degree, value in poly.items() if value}
    if len(result) > MAX_TERMS:
        raise ExactMathError(f"化简后的多项式项数不能超过 {MAX_TERMS}。")
    if result and max(result) > MAX_DEGREE:
        raise ExactMathError(f"多项式次数不能超过 {MAX_DEGREE}。")
    return result


def normalize_polynomial_expression(expression: str) -> str:
    text = str(expression or "").strip().replace("−", "-").replace("－", "-").replace("×", "*")
    text = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+", lambda match: "**" + match.group().translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")), text)
    text = re.sub(r"\s+", "", text).replace("^", "**")
    # Accept conventional implicit products such as 3x, x(x+1), and (x+1)2.
    text = re.sub(r"(?<=[0-9])(?=x|\()|(?<=x)(?=x|\()|(?<=\))(?=[0-9x(])", "*", text)
    return text


def _parse_polynomial(expression: str) -> tuple[str, Polynomial]:
    normalized = normalize_polynomial_expression(expression)
    if not normalized or len(normalized) > MAX_EXPRESSION_LENGTH:
        raise ExactMathError(f"多项式不能为空且长度不能超过 {MAX_EXPRESSION_LENGTH} 个字符。")
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise ExactMathError("多项式表达式语法无效。") from exc
    if sum(1 for _ in ast.walk(tree)) > 128:
        raise ExactMathError("多项式表达式结构过于复杂。")

    def visit(node: ast.AST) -> Polynomial:
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            if abs(node.value) > 10**12:
                raise ExactMathError("整数系数绝对值不能超过 10^12。")
            return {0: Fraction(node.value)} if node.value else {}
        if isinstance(node, ast.Name) and node.id == "x":
            return {1: Fraction(1)}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            result = visit(node.operand)
            return result if isinstance(node.op, ast.UAdd) else {degree: -value for degree, value in result.items()}
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                result = dict(left)
                for degree, value in right.items():
                    result[degree] = result.get(degree, Fraction(0)) + value
                return _clean(result)
            if isinstance(node.op, ast.Sub):
                result = dict(left)
                for degree, value in right.items():
                    result[degree] = result.get(degree, Fraction(0)) - value
                return _clean(result)
            if isinstance(node.op, ast.Mult):
                result: Polynomial = {}
                for left_degree, left_value in left.items():
                    for right_degree, right_value in right.items():
                        degree = left_degree + right_degree
                        if degree > MAX_DEGREE:
                            raise ExactMathError(f"多项式次数不能超过 {MAX_DEGREE}。")
                        result[degree] = result.get(degree, Fraction(0)) + left_value * right_value
                return _clean(result)
            if isinstance(node.op, ast.Div):
                if set(right) - {0}:
                    raise ExactMathError("只支持除以非零常数，不支持含变量的分母。")
                divisor = right.get(0, Fraction(0))
                if divisor == 0:
                    raise ExactMathError("表达式包含除零。")
                return _clean({degree: value / divisor for degree, value in left.items()})
            if isinstance(node.op, ast.Pow):
                if set(right) - {0}:
                    raise ExactMathError("多项式指数必须是常数整数。")
                exponent = right.get(0, Fraction(0))
                if exponent.denominator != 1 or exponent < 0 or exponent > MAX_DEGREE:
                    raise ExactMathError(f"多项式指数必须是 0 到 {MAX_DEGREE} 之间的整数。")
                result: Polynomial = {0: Fraction(1)}
                for _ in range(int(exponent)):
                    product: Polynomial = {}
                    for left_degree, left_value in result.items():
                        for right_degree, right_value in left.items():
                            degree = left_degree + right_degree
                            if degree > MAX_DEGREE:
                                raise ExactMathError(f"多项式次数不能超过 {MAX_DEGREE}。")
                            product[degree] = product.get(degree, Fraction(0)) + left_value * right_value
                    result = _clean(product)
                return result
        raise ExactMathError("只支持变量 x、整数常数以及多项式的 + - * / ** 运算。")

    return normalized, _clean(visit(tree.body))


def _format_fraction(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def format_polynomial(poly: Polynomial) -> str:
    pieces: list[str] = []
    for degree in sorted(poly, reverse=True):
        coefficient = poly[degree]
        absolute = abs(coefficient)
        if degree == 0:
            term = _format_fraction(absolute)
        else:
            variable = "x" if degree == 1 else f"x**{degree}"
            term = variable if absolute == 1 else f"{_format_fraction(absolute)}*{variable}"
        if not pieces:
            pieces.append(f"-{term}" if coefficient < 0 else term)
        else:
            pieces.append((" - " if coefficient < 0 else " + ") + term)
    return "".join(pieces) or "0"


def polynomial_latex(expression: str) -> str:
    """Render a validated polynomial; callers retain raw replay expressions."""
    _, poly = _parse_polynomial(expression)
    return _polynomial_latex(poly)


def _polynomial_latex(poly: Polynomial) -> str:
    text = format_polynomial(poly)
    text = re.sub(r"(\d+)/(\d+)", lambda match: r"\frac{" + match[1] + "}{" + match[2] + "}", text)
    text = re.sub(r"\*\*(\d+)", lambda match: "^{" + match[1] + "}", text)
    return text.replace("*", r"\cdot ")


def _fraction_bound(value: str | int | Fraction) -> Fraction:
    if isinstance(value, Fraction):
        result = value
    elif isinstance(value, int) and not isinstance(value, bool):
        result = Fraction(value)
    elif isinstance(value, str) and len(value.strip()) <= 32:
        try:
            result = Fraction(value.strip())
        except (ValueError, ZeroDivisionError) as exc:
            raise ExactMathError("积分上下限必须是整数或有理数（例如 -1、1/2）。") from exc
    else:
        raise ExactMathError("积分上下限必须是整数或有理数（例如 -1、1/2）。")
    return _check_coefficient(result)


def verify_polynomial_identity(left: str, right: str) -> dict:
    """Compare exact rational coefficients, never infer identity from samples."""
    normalized_left, lhs = _parse_polynomial(left)
    normalized_right, rhs = _parse_polynomial(right)
    difference = dict(lhs)
    for degree, coefficient in rhs.items():
        difference[degree] = difference.get(degree, Fraction(0)) - coefficient
    difference = _clean(difference)
    return {
        **_provenance("polynomial_identity", {"left": left, "right": right}),
        "left": normalized_left, "right": normalized_right,
        "difference": format_polynomial(difference), "identity": not difference,
        "status": "symbolically_verified" if not difference else "identity_disproved",
        "evidence_type": "polynomial_identity", "method": "exact_rational_coefficient_comparison",
        "exact": True,
        "assumptions": "变量 x 为实数；仅覆盖有理数系数单变量多项式（次数不超过 12）。比较全部系数，不是有限样本检查，也不是 Lean 形式化证明。",
    }


def differentiate_polynomial(expression: str, variable: str = "x") -> dict:
    if variable != "x":
        raise ExactMathError("目前只支持对变量 x 求导。")
    normalized, poly = _parse_polynomial(expression)
    derivative = _clean({degree - 1: coefficient * degree for degree, coefficient in poly.items() if degree})
    return {
        **_provenance("differentiate", {"expression": expression, "variable": variable}),
        "operation": "differentiate", "expression": normalized, "variable": variable,
        "derivative": format_polynomial(derivative), "status": "computed",
        "evidence_type": "symbolic_derivative", "method": "bounded_polynomial_ast",
        "exact": True, "assumptions": "仅对次数不超过 12 的单变量多项式做符号求导；结果是精确代数运算，不是形式化证明。",
    }


def integrate_polynomial_definite(expression: str, lower: str | int | Fraction, upper: str | int | Fraction, variable: str = "x") -> dict:
    if variable != "x":
        raise ExactMathError("目前只支持对变量 x 积分。")
    normalized, poly = _parse_polynomial(expression)
    lo, hi = _fraction_bound(lower), _fraction_bound(upper)
    if abs(lo) > 10**6 or abs(hi) > 10**6:
        raise ExactMathError("积分上下限绝对值不能超过 10^6。")
    antiderivative = {degree + 1: coefficient / (degree + 1) for degree, coefficient in poly.items()}

    def evaluate(point: Fraction) -> Fraction:
        return sum((coefficient * point**degree for degree, coefficient in antiderivative.items()), Fraction(0))

    value = _check_coefficient(evaluate(hi) - evaluate(lo))
    return {
        **_provenance("integrate_definite", {"expression": expression, "lower": str(lower), "upper": str(upper), "variable": variable}),
        "operation": "integrate_definite", "expression": normalized, "variable": variable,
        "lower": _format_fraction(lo), "upper": _format_fraction(hi),
        "antiderivative": format_polynomial(antiderivative), "value": _format_fraction(value),
        "expression_latex": _polynomial_latex(poly), "antiderivative_latex": _polynomial_latex(antiderivative),
        "status": "computed", "evidence_type": "exact_definite_integral",
        "method": "bounded_polynomial_antiderivative", "exact": True,
        "assumptions": "变量 x 为实数，被积函数是次数不超过 12 的有理数系数多项式；上下限为有理数且绝对值不超过 10^6；按原函数定理精确计算定积分，不是形式化证明。",
    }
