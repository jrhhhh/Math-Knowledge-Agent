"""Lightweight delimiter checks for Markdown/LaTeX emitted by the model."""
import re


def validate_formula(text: str) -> dict:
    text = text or ""
    issues = []
    if text.count("$") % 2:
        issues.append("美元定界符未配对")
    for left, right, name in [(r"\\(", r"\\)", "行内公式"), (r"\\[", r"\\]", "独立公式")]:
        if text.count(left) != text.count(right):
            issues.append(f"{name}定界符未配对")
    opens, closes = text.count("{"), text.count("}")
    if opens != closes:
        issues.append("花括号未配对")
    begins = re.findall(r"\\begin\{([^}]+)\}", text)
    ends = re.findall(r"\\end\{([^}]+)\}", text)
    if sorted(begins) != sorted(ends):
        issues.append("LaTeX 环境未配对")
    return {"valid": not issues, "issues": issues}
