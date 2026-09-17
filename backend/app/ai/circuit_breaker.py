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


def before_call():
    with _lock:
        if _opened_at and time.monotonic() - _opened_at < _cooldown:
            raise CircuitOpenError("DeepSeek 熔断中，将使用本地数学兜底。")


def success():
    global _failures, _opened_at
    with _lock:
        _failures = 0
        _opened_at = 0.0


def failure():
    global _failures, _opened_at
    with _lock:
        _failures += 1
        if _failures >= _threshold:
            _opened_at = time.monotonic()


def snapshot():
    with _lock:
        age = time.monotonic() - _opened_at if _opened_at else None
        return {"state": "open" if age is not None and age < _cooldown else "closed", "failure_streak": _failures, "cooldown_seconds": _cooldown, "remaining_seconds": round(max(0.0, _cooldown - age), 1) if age is not None else 0.0}
