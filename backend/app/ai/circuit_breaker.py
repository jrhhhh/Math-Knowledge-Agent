"""Process-local circuit breaker for a temporarily unavailable model provider."""
import time
from threading import Lock


class CircuitOpenError(RuntimeError):
    pass


_lock = Lock()
_failures = 0
_opened_at = 0.0
_threshold = 3
_cooldown = 30.0
_half_open = False


def before_call():
    global _half_open, _opened_at
    with _lock:
        if not _opened_at:
            return
        elapsed = time.monotonic() - _opened_at
        if elapsed < _cooldown:
            raise CircuitOpenError("DeepSeek 熔断中，将使用本地数学兜底。")
        if _half_open:
            raise CircuitOpenError("DeepSeek 正在进行恢复探测，将使用备用模型或本地数学兜底。")
        _half_open = True


def success():
    global _failures, _opened_at, _half_open
    with _lock:
        _failures = 0
        _opened_at = 0.0
        _half_open = False


def failure():
    global _failures, _opened_at, _half_open
    with _lock:
        _failures += 1
        if _failures >= _threshold:
            _opened_at = time.monotonic()
            _half_open = False


def snapshot():
    with _lock:
        age = time.monotonic() - _opened_at if _opened_at else None
        if age is not None and age < _cooldown:
            state = "open"
        elif _half_open:
            state = "half_open"
        else:
            state = "closed"
        return {"state": state, "failure_streak": _failures, "cooldown_seconds": _cooldown, "remaining_seconds": round(max(0.0, _cooldown - age), 1) if age is not None else 0.0}
