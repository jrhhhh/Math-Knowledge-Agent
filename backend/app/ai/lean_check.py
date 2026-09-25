from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


LEAN_THEOREMS = {
    "nat_add_zero": "example (n : Nat) : n + 0 = n := by simp",
    "nat_zero_add": "example (n : Nat) : 0 + n = n := by simp",
}


def check_known_theorem(theorem: str) -> dict:
    source = LEAN_THEOREMS.get(theorem)
    if source is None:
        raise ValueError("只支持已登记的 Lean theorem 模板。")
    lean = shutil.which("lean")
    if not lean:
        return {"status": "unavailable", "theorem": theorem, "reason": "lean_not_found", "evidence_type": "formal_verification"}
    with tempfile.TemporaryDirectory(prefix="math-agent-lean-") as directory:
        path = Path(directory) / "Check.lean"
        path.write_text(source + "\n", encoding="utf-8")
        try:
            completed = subprocess.run([lean, str(path)], capture_output=True, text=True, timeout=8)
        except subprocess.TimeoutExpired:
            return {"status": "tool_timeout", "theorem": theorem, "evidence_type": "formal_verification"}
    output = (completed.stdout + completed.stderr).strip()
    return {
        "status": "formally_verified" if completed.returncode == 0 else "formal_check_failed",
        "theorem": theorem,
        "evidence_type": "formal_verification",
        "method": "lean_fixed_template",
        "details": output or "Lean completed without diagnostics.",
        "assumptions": "仅验证项目登记的固定 Lean theorem 模板。",
    }
