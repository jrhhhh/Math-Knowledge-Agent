from collections import deque
from datetime import datetime, timezone
from threading import Lock


_lock = Lock()
_recent_failures = deque(maxlen=50)
_metrics = {"requests": 0, "successes": 0, "failures": 0, "retries": 0, "slow_requests": 0, "duration_total": 0.0, "first_token_total": 0.0, "first_token_samples": 0, "backups_succeeded": 0, "backups_failed": 0, "last_backup_timestamp": 0}

def record_backup(success: bool):
    with _lock:
        _metrics["backups_succeeded" if success else "backups_failed"] += 1
        if success:
            _metrics["last_backup_timestamp"] = int(datetime.now(timezone.utc).timestamp())


def record_request(success: bool, retries: int = 0, error: str | None = None, duration: float | None = None, first_token: float | None = None):
    with _lock:
        _metrics["requests"] += 1
        _metrics["retries"] += retries
        _metrics["successes" if success else "failures"] += 1
        if duration is not None and duration >= 20:
            _metrics["slow_requests"] += 1
        if duration is not None:
            _metrics["duration_total"] += duration
        if first_token is not None:
            _metrics["first_token_total"] += first_token
            _metrics["first_token_samples"] += 1
        if not success:
            _recent_failures.append({"at": datetime.now(timezone.utc).isoformat(), "error": error or "unknown"})


def snapshot():
    with _lock:
        return {**_metrics, "recent_failures": list(_recent_failures)}
