"""Fast heuristic quality signals for generated mathematical answers."""
import re


def evaluate_answer(answer: str, question: str = "") -> dict:
    text = (answer or "").strip()
    is_proof = bool(re.search(r"证明|证明题|推导|prove|proof", question or "", re.I))
    checks = {
        "has_conclusion": bool(re.search(r"结论|因此|故|所以", text)),
        "has_conditions": bool(re.search(r"条件|设|若|假设|其中", text)),
        "has_reasoning": bool(re.search(r"证明|推导|由此|因为|由于|定理", text)),
        "has_formula": bool(re.search(r"\\[a-zA-Z]+|[=≤≥∈⊂→]|\$", text)),
    }
    if is_proof:
        checks.update({
            "has_basis": bool(re.search(r"由|根据|定理|引理|定义", text)),
            "has_derivation": bool(re.search(r"于是|从而|因此|可得|整理", text)),
        })
    score = round(sum(checks.values()) / len(checks), 2)
    return {"score": score, "checks": checks, "question_type": "proof" if is_proof else "general", "level": "good" if score >= 0.75 else ("partial" if score >= 0.5 else "weak")}
