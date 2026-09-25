from __future__ import annotations

import importlib.util
import shutil
import subprocess


def _command_status(command: str, version_args: list[str] | None = None) -> dict:
    path = shutil.which(command)
    if not path:
        return {"available": False, "reason": "command_not_found"}
    try:
        result = subprocess.run([path, *(version_args or ["--version"])], capture_output=True, text=True, timeout=3)
        output = (result.stdout or result.stderr).strip().splitlines()
        return {"available": result.returncode == 0, "path": path, "version": output[0][:240] if output else None, "reason": None if result.returncode == 0 else "command_failed"}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "path": path, "reason": type(exc).__name__}


def capability_snapshot() -> dict:
    python_tools = {name: {"available": importlib.util.find_spec(name) is not None} for name in ("sympy", "osqp", "cvxpy")}
    commands = {"lean": _command_status("lean"), "sage": _command_status("sage")}
    return {"tools": {**python_tools, **commands}, "formal_verification": {"lean": commands["lean"], "sage": commands["sage"]}, "disclaimer": "available 表示运行时探测到工具，不表示任意数学结论已经验证。"}
