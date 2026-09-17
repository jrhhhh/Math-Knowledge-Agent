from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4


_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="math-agent-retry")
_lock = Lock()
_jobs = {}


def _now():
    return datetime.now(timezone.utc).isoformat()


def enqueue(operation: str, question: str, max_attempts: int = 3):
    job_id = uuid4().hex[:12]
    job = {"id": job_id, "operation": operation, "question": question, "status": "queued", "attempts": 0, "max_attempts": max_attempts, "error": None, "result": None, "created_at": _now(), "updated_at": _now()}
    with _lock:
        _jobs[job_id] = job
    _executor.submit(_run, job_id)
    return job.copy()


def get_job(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
        return job.copy() if job else None


def _run(job_id: str):
    from app.api.ai import get_related_graph
    from app.database import SessionLocal
    from app.api.ai import RelatedGraphRequest

    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = "running"
        job["updated_at"] = _now()
    while job["attempts"] < job["max_attempts"]:
        job["attempts"] += 1
        db = SessionLocal()
        try:
            if job["operation"] != "related_graph":
                raise ValueError("不支持的重试操作")
            result = get_related_graph(RelatedGraphRequest(question=job["question"]), db)
            job["status"] = "succeeded"
            job["result"] = {"candidate_id": result.get("candidate_id"), "knowledge_graph": result.get("knowledge_graph")}
            job["error"] = None
            break
        except Exception as exc:
            job["error"] = str(exc)
            job["status"] = "retrying" if job["attempts"] < job["max_attempts"] else "failed"
        finally:
            db.close()
            job["updated_at"] = _now()


def snapshot():
    with _lock:
        return [job.copy() for job in _jobs.values()]
