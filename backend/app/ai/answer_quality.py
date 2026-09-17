"""Fast heuristic quality signals for generated mathematical answers."""
import re


def evaluate_answer(answer: str) -> dict:
    text = (answer or "").strip()
    checks = {
        "has_conclusion": bool(re.search(r"结论|因此|故|所以", text)),
        "has_conditions": bool(re.search(r"条件|设|若|假设|其中", text)),
        "has_reasoning": bool(re.search(r"证明|推导|由此|因为|由于|定理", text)),
        "has_formula": bool(re.search(r"\\[a-zA-Z]+|[=≤≥∈⊂→]|\$", text)),
    }
    score = round(sum(checks.values()) / len(checks), 2)
    return {"score": score, "checks": checks, "level": "good" if score >= 0.75 else ("partial" if score >= 0.5 else "weak")}
