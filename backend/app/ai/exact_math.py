"""Small, deterministic exact arithmetic tool for explicitly bounded inputs."""
from __future__ import annotations

import ast
from fractions import Fraction
import operator

_BIN_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: Fraction, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class ExactMathError(ValueError):
    pass


def _evaluate(node: ast.AST, variables: dict[str, int] | None = None):
    variables = variables or {}
    if isinstance(node, ast.Name) and node.id in variables:
        return variables[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        if abs(node.value) > 10**12:
            raise ExactMathError("整数绝对值不能超过 10^12。")
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_evaluate(node.operand, variables))
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left, right = _evaluate(node.left, variables), _evaluate(node.right, variables)
        if isinstance(node.op, ast.Pow) and (right < 0 or abs(right) > 12):
            raise ExactMathError("幂指数必须是 0 到 12 之间的整数。")
        value = _BIN_OPS[type(node.op)](left, right)
        if isinstance(value, (int, float)) and abs(value) > 10**18:
            raise ExactMathError("中间结果绝对值不能超过 10^18。")
        return value
    raise ExactMathError("只支持整数、括号和 + - * / // % ** 运算。")


def evaluate_exact(expression: str) -> dict:
    expression = expression.strip()
    if not expression or len(expression) > 240:
        raise ExactMathError("表达式不能为空且长度不能超过 240 个字符。")
    try:
        tree = ast.parse(expression, mode="eval")
        value = _evaluate(tree.body)
    except ZeroDivisionError as exc:
        raise ExactMathError("表达式包含除零。") from exc
    except SyntaxError as exc:
        raise ExactMathError("表达式语法无效。") from exc
    serialized_value = value.numerator if isinstance(value, Fraction) and value.denominator == 1 else str(value) if isinstance(value, Fraction) else value
    return {"expression": expression, "value": serialized_value, "exact": True, "evidence_type": "computed", "status": "computed", "method": "bounded_rational_ast", "assumptions": "输入只包含整数和受限算术运算；除法以有理数精确计算；未执行任意代码。"}


def check_identity(left: str, right: str, variable: str = "x", start: int = -10, end: int = 10) -> dict:
    """Search a bounded integer range for a counterexample to left == right."""
    if variable != "x" or not left.strip() or not right.strip():
        raise ExactMathError("目前只支持变量 x，且两侧表达式不能为空。")
    if end < start or end - start > 200:
        raise ExactMathError("检查区间必须递增且长度不能超过 200。")
    try:
        left_tree, right_tree = ast.parse(left.strip(), mode="eval"), ast.parse(right.strip(), mode="eval")
        for value in range(start, end + 1):
            left_value = _evaluate(left_tree.body, {variable: value})
            right_value = _evaluate(right_tree.body, {variable: value})
            if left_value != right_value:
                return {"left": left, "right": right, "variable": variable, "range": [start, end], "status": "counterexample_found", "counterexample": {variable: value, "left_value": left_value, "right_value": right_value}, "evidence_type": "counterexample_search", "method": "bounded_integer_exhaustive", "assumptions": "只对给定整数区间逐点检查；未证明区间外成立。"}
    except (SyntaxError, ZeroDivisionError, TypeError) as exc:
        raise ExactMathError("表达式无效或在检查区间内出现除零。") from exc
    return {"left": left, "right": right, "variable": variable, "range": [start, end], "status": "no_counterexample_in_range", "counterexample": None, "evidence_type": "counterexample_search", "method": "bounded_integer_exhaustive", "assumptions": "只对给定整数区间逐点检查；未证明区间外成立。"}
