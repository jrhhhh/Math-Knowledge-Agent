"""Controlled action planning for the mathematical agent.

The planner only selects from an allowlist. It does not execute tools and does
not claim that a mathematical goal is complete.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


ALLOWED_ACTIONS = {
    "retrieve_knowledge",
    "exact_arithmetic",
    "exact_calculus",
    "polynomial_identity",
    "counterexample_search",
    "lean_check",
    "draft_proof",
    "review_proof",
    "revise_answer",
    "review_revise_review",
    "request_clarification",
    "stop_inconclusive",
}


@dataclass(frozen=True)
class AgentAction:
    name: str
    reason: str
    parameters: dict


_ARITHMETIC_CANDIDATE = re.compile(r"[（(]*[0-9０-９][0-9０-９\s+\-－−—*/×÷%().（）^]*[0-9０-９）)]")
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")


def extract_arithmetic_expression(text: str) -> str | None:
    """Extract a bounded arithmetic expression from natural-language input.

    This only normalizes syntax. The exact-math evaluator remains the security
    boundary and rejects names, calls, and unsupported AST nodes.
    """
    candidates: list[str] = []
    for match in _ARITHMETIC_CANDIDATE.finditer(text.translate(_FULLWIDTH_DIGITS)):
        candidate = match.group(0).strip().translate(str.maketrans({
            "×": "*", "÷": "/", "－": "-", "−": "-", "—": "-", "（": "(", "）": ")",
        }))
        candidate = re.sub(r"(?<!\*)\^(?!\*)", "**", candidate)
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if any(operator in candidate for operator in ("+", "-", "*", "/", "%")):
            candidates.append(candidate)
    return candidates[-1] if candidates else None


_CALCULUS_BOUND = r"[+-]?\d+(?:\s*/\s*[+-]?\d+)?"


def _parse_calculus_expression(value: str) -> str:
    expression = value.strip().rstrip("。.")
    expression = re.sub(r"^.*?f\(x\)\s*=\s*", "", expression)
    expression = re.sub(r"^(?:函数|表达式)\s*", "", expression)
    return expression.strip()


def extract_calculus_request(question: str, parameters: dict | None = None) -> dict | None:
    """Recognize a deliberately small, explicit polynomial-calculus request."""
    supplied = parameters or {}
    operation = supplied.get("operation")
    expression = supplied.get("expression")
    if operation in {"differentiate", "derivative", "求导"}:
        return {"operation": "differentiate", "expression": expression} if expression else None
    if operation in {"integrate_definite", "definite_integral", "定积分"}:
        return {"operation": "integrate_definite", "expression": expression, "lower": supplied.get("lower"), "upper": supplied.get("upper")}

    text = question.strip().rstrip("。.!?！？；;").strip()
    text = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+", lambda match: "**" + match.group().translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")), text)
    integral = re.search(
        rf"(?:求|计算)?\s*(?:定积分|积分)\s*[:：]?\s*(.+?)\s*[，,;；]?\s*x\s*从\s*({_CALCULUS_BOUND})\s*到\s*({_CALCULUS_BOUND})\s*$",
        text,
    )
    if integral:
        return {"operation": "integrate_definite", "expression": _parse_calculus_expression(integral.group(1)), "lower": integral.group(2), "upper": integral.group(3)}

    incomplete_integral = re.fullmatch(r"(?:求|计算)?\s*定积分\s*[:：]?\s*([^，,;；]+)", text)
    if incomplete_integral:
        return {"operation": "integrate_definite", "expression": _parse_calculus_expression(incomplete_integral.group(1)), "lower": None, "upper": None}

    derivative = re.search(r"(?:求导数|求导|微分)\s*[:：]?\s*(.+)$", text)
    if derivative:
        return {"operation": "differentiate", "expression": _parse_calculus_expression(derivative.group(1))}
    return None


def plan_next_action(
    question: str,
    *,
    evidence: list[dict] | None = None,
    iterations: int = 0,
    parameters: dict | None = None,
) -> dict:
    """Return one bounded next action and explicit stopping rules."""
    text = question.strip()
    evidence = evidence or []
    parameters = parameters or {}
    if not text:
        raise ValueError("问题不能为空。")
    if iterations >= 8:
        action = AgentAction("stop_inconclusive", "已达到单任务最大规划轮数，现有证据不足以继续。", {})
    elif parameters.get("operation") == "polynomial_identity" or "多项式恒等" in text:
        sides = dict(parameters)
        equality = re.fullmatch(r"(?:检查|验证|判断)?\s*多项式恒等式\s*[:：]?\s*([^=]+)=([^=]+)", text)
        if equality:
            sides.setdefault("left", equality.group(1).strip())
            sides.setdefault("right", equality.group(2).strip())
        if sides.get("left") and sides.get("right"):
            action = AgentAction("polynomial_identity", "比较有理数系数多项式的全部系数，不使用有限样本推断恒等。", {"left": sides["left"], "right": sides["right"]})
        else:
            action = AgentAction("request_clarification", "请提供多项式恒等式的左右两侧。", {"missing": [key for key in ("left", "right") if not sides.get(key)]})
    elif parameters.get("operation") in {"differentiate", "derivative", "求导", "integrate_definite", "definite_integral", "定积分"} or (any(word in text for word in ("积分", "求导", "导数", "微分")) and not any(word in text for word in ("证明", "为什么"))):
        calculus = extract_calculus_request(text, parameters)
        if calculus and calculus.get("expression") and (calculus["operation"] != "integrate_definite" or all(calculus.get(key) is not None for key in ("lower", "upper"))):
            action = AgentAction("exact_calculus", "题目是受限单变量多项式的符号求导或定积分，调用本地精确微积分工具。", calculus)
        else:
            missing = ["expression"]
            if calculus and calculus.get("operation") == "integrate_definite":
                missing = [key for key in ("expression", "lower", "upper") if calculus.get(key) is None or calculus.get(key) == ""]
            action = AgentAction("request_clarification", "目前本地微积分工具要求给出多项式；定积分还需明确变量 x 的上下限，例如‘求定积分 x^2，x 从 0 到 1’。", {"missing": missing})
    elif any(word in text for word in ("计算", "求值", "等于多少", "分解")):
        expression = parameters.get("expression") or extract_arithmetic_expression(text)
        if expression:
            action = AgentAction("exact_arithmetic", "问题包含明确计算目标，先执行受限精确计算。", {"expression": expression})
        else:
            action = AgentAction("request_clarification", "未能从问题或参数中识别可安全计算的表达式。", {"missing": ["expression"]})
    elif any(word in text for word in ("Lean", "形式化", "可形式化")):
        action = AgentAction("lean_check", "问题明确要求形式化检查，选择已登记的 Lean 模板验证。", {"question": text})
    elif any(word in text for word in ("证明", "推导", "为什么")):
        proof = parameters.get("proof")
        if not proof:
            for item in reversed(evidence):
                result = item.get("result", item)
                if item.get("action") == "draft_proof" and result.get("proof"):
                    proof = result["proof"]
                    break
        has_retrieval = any(item.get("action") == "retrieve_knowledge" for item in evidence)
        has_review = any(item.get("action") in {"review_proof", "review_revise_review"} for item in evidence)
        if has_review:
            action = AgentAction("stop_inconclusive", "证明已完成模型或本地结构审查；当前审查不足以单独构成数学正确性证明。", {})
        elif proof:
            action = AgentAction("review_revise_review", "对已有证明执行审查；发现问题时最多修订一次并再次审查。", {"proof": proof})
        elif has_retrieval:
            retrieved = next((item.get("result", {}) for item in reversed(evidence) if item.get("action") == "retrieve_knowledge"), {})
            action = AgentAction("draft_proof", "已完成知识检索，下一步生成明确标记为待验证的证明草稿。", {
                "question": text,
                "concepts": retrieved.get("concepts", []),
                "sources": retrieved.get("sources", []),
            })
        else:
            action = AgentAction("retrieve_knowledge", "先检索定义、定理和教材依据，再决定证明步骤。", {"query": text})
    elif any(word in text for word in ("是否恒等", "恒等", "反例", "对任意", "所有", "总是", "一定", "是否成立")):
        if parameters.get("left") and parameters.get("right"):
            action = AgentAction("counterexample_search", "比较明确给出的两侧表达式，并在有限整数区间搜索反例。", {"left": parameters["left"], "right": parameters["right"], "range": parameters.get("range", [-10, 10])})
        else:
            action = AgentAction("request_clarification", "有限反例搜索需要明确给出待比较的两个表达式。", {"missing": ["left", "right"]})
    elif not evidence:
        action = AgentAction("retrieve_knowledge", "先查找本地已审核知识和教材片段，明确题目所需定义与条件。", {"query": text})
    else:
        action = AgentAction("request_clarification", "题目缺少可识别的计算或证明目标，需要补充对象、条件或定义域。", {"missing": ["目标", "必要条件或定义域"]})
    if action.name not in ALLOWED_ACTIONS:
        raise RuntimeError("planner produced an action outside the allowlist")
    return {
        "action": action.name,
        "reason": action.reason,
        "parameters": action.parameters,
        "iteration": iterations,
        "allowed_actions": sorted(ALLOWED_ACTIONS),
        "stop_conditions": [
            "发现满足前提的反例时停止并标记 refuted",
            "缺少必要条件时停止并请求澄清",
            "达到 8 轮或总预算时标记 inconclusive",
            "只有满足题型验收条件并附带证据时才能 completed_with_evidence",
        ],
    }
