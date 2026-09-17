from collections import deque
from datetime import datetime, timezone
from threading import Lock


_lock = Lock()
_recent_failures = deque(maxlen=50)
_metrics = {"requests": 0, "successes": 0, "failures": 0, "retries": 0, "slow_requests": 0, "duration_total": 0.0, "first_token_total": 0.0, "first_token_samples": 0, "backups_succeeded": 0, "backups_failed": 0, "last_backup_timestamp": 0}
_providers = {
    "primary": {"state": "unknown", "successes": 0, "failures": 0, "last_error": None, "last_success_at": None, "last_failure_at": None},
    "backup": {"state": "unknown", "successes": 0, "failures": 0, "last_error": None, "last_success_at": None, "last_failure_at": None},
}

def record_backup(success: bool):
    with _lock:
        _metrics["backups_succeeded" if success else "backups_failed"] += 1
        if success:
            _metrics["last_backup_timestamp"] = int(datetime.now(timezone.utc).timestamp())


def record_request(success: bool, retries: int = 0, error: str | None = None, duration: float | None = None, first_token: float | None = None, provider: str = "primary"):
    with _lock:
        provider_metrics = _providers.setdefault(provider, {"state": "unknown", "successes": 0, "failures": 0, "last_error": None, "last_success_at": None, "last_failure_at": None})
        now = datetime.now(timezone.utc).isoformat()
        provider_metrics["state"] = "healthy" if success else "degraded"
        provider_metrics["successes" if success else "failures"] += 1
        if success:
            provider_metrics["last_success_at"] = now
        else:
            provider_metrics["last_failure_at"] = now
            provider_metrics["last_error"] = error or "unknown"
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
        return {**_metrics, "recent_failures": list(_recent_failures), "providers": {name: dict(value) for name, value in _providers.items()}}
