from collections import deque
from datetime import datetime, timezone
from threading import Lock


_lock = Lock()
_recent_failures = deque(maxlen=50)
_metrics = {"requests": 0, "successes": 0, "failures": 0, "retries": 0}


def record_request(success: bool, retries: int = 0, error: str | None = None):
    with _lock:
        _metrics["requests"] += 1
        _metrics["retries"] += retries
        _metrics["successes" if success else "failures"] += 1
        if not success:
            _recent_failures.append({"at": datetime.now(timezone.utc).isoformat(), "error": error or "unknown"})


def snapshot():
    with _lock:
        return {**_metrics, "recent_failures": list(_recent_failures)}
