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


def plan_next_action(question: str, *, evidence: list[dict] | None = None, iterations: int = 0) -> dict:
    """Return one bounded next action and explicit stopping rules."""
    text = question.strip()
    evidence = evidence or []
    if not text:
        raise ValueError("问题不能为空。")
    if iterations >= 8:
        action = AgentAction("stop_inconclusive", "已达到单任务最大规划轮数，现有证据不足以继续。", {})
    elif any(word in text for word in ("计算", "求值", "等于多少", "分解")):
        parameters = {"question": text}
        expression = extract_arithmetic_expression(text)
        if expression:
            parameters["expression"] = expression
        action = AgentAction("exact_arithmetic", "问题包含明确计算意图，先执行受限精确计算。", parameters)
    elif any(word in text for word in ("Lean", "形式化", "可形式化")):
        action = AgentAction("lean_check", "问题明确要求形式化检查，选择已登记的 Lean 模板验证。", {"question": text})
    elif any(word in text for word in ("是否恒等", "恒等式", "对任意", "所有", "证明")):
        action = AgentAction("counterexample_search", "先在受限整数范围搜索反例；找到反例时停止错误命题的证明。", {"question": text, "range": [-10, 10]})
    elif not evidence:
        action = AgentAction("retrieve_knowledge", "先查找本地已审核知识和教材片段，明确题目所需定义与条件。", {"query": text})
    elif any(word in text for word in ("证明", "推导", "为什么")):
        action = AgentAction("draft_proof", "整理目标、假设和可用定义后形成待审查证明草稿。", {"question": text})
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
