from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4
import json
import time
import os
from queue import PriorityQueue

from app.database import SessionLocal
from app.models.ai_retry_job import AIRetryJob


_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="math-agent-retry")
_pending = PriorityQueue()
_lock = Lock()
_jobs = {}
_last_attempt = 0.0
try:
    RETRY_BACKOFF_MAX_SECONDS = max(1.5, float(os.getenv("MATH_AGENT_RETRY_BACKOFF_MAX_SECONDS", "30")))
except (TypeError, ValueError):
    RETRY_BACKOFF_MAX_SECONDS = 30.0


def _now():
    return datetime.now(timezone.utc).isoformat()


def enqueue(operation: str, question: str, max_attempts: int = 3, priority: int = 0, conversation_id: int | None = None):
    job_id = uuid4().hex[:12]
    job = {"id": job_id, "operation": operation, "question": question, "conversation_id": conversation_id, "status": "queued", "attempts": 0, "max_attempts": max_attempts, "error": None, "result": None, "created_at": _now(), "updated_at": _now()}
    with _lock:
        _jobs[job_id] = job
        terminal = [key for key, value in _jobs.items() if value["status"] in {"succeeded", "failed", "cancelled"}]
        for key in terminal[:-100]:
            _jobs.pop(key, None)
    db = SessionLocal()
    try:
        db.add(AIRetryJob(id=job_id, operation=operation, question=question, conversation_id=conversation_id, max_attempts=max_attempts))
        db.commit()
    finally:
        db.close()
    _pending.put((-priority, job_id))
    # Contract tests can persist and inspect a queued job without starting a
    # real provider call or leaving a non-terminating worker at interpreter
    # shutdown. Production keeps the normal asynchronous behavior.
    if os.getenv("MATH_AGENT_DISABLE_RETRY_WORKER", "0").lower() not in {"1", "true", "yes"}:
        _executor.submit(_worker)
    return job.copy()


def get_job(job_id: str):
    db = SessionLocal()
    try:
        stored = db.query(AIRetryJob).filter(AIRetryJob.id == job_id).first()
        if stored:
            return {"id": stored.id, "operation": stored.operation, "question": stored.question, "status": stored.status, "attempts": stored.attempts, "max_attempts": stored.max_attempts, "error": stored.error, "result": json.loads(stored.result_json) if stored.result_json else None, "created_at": stored.created_at.isoformat() if stored.created_at else None, "updated_at": stored.updated_at.isoformat() if stored.updated_at else None}
    finally:
        db.close()


def cancel_job(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
        if job:
            job["status"] = "cancelled"
            job["updated_at"] = _now()
            _persist(job)
            return job.copy()
    db = SessionLocal()
    try:
        stored = db.query(AIRetryJob).filter(AIRetryJob.id == job_id).first()
        if stored and stored.status in {"queued", "running", "retrying"}:
            stored.status = "cancelled"
            db.commit()
            return get_job(job_id)
    finally:
        db.close()
    return None
    with _lock:
        job = _jobs.get(job_id)
        return job.copy() if job else None


def _run(job_id: str):
    from app.api.ai import get_related_graph, _ask_impl
    from app.database import SessionLocal
    from app.api.ai import RelatedGraphRequest, AskRequest

    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = "running"
        job["updated_at"] = _now()
    _persist(job)
    global _last_attempt
    while job["attempts"] < job["max_attempts"]:
        if job["status"] == "cancelled":
            _persist(job)
            return
        job["attempts"] += 1
        exponential_wait = min(RETRY_BACKOFF_MAX_SECONDS, 1.5 * (2 ** max(job["attempts"] - 1, 0)))
        wait_for = max(0.0, exponential_wait - (time.monotonic() - _last_attempt))
        if wait_for:
            time.sleep(wait_for)
        _last_attempt = time.monotonic()
        db = SessionLocal()
        try:
            if job["operation"] == "answer":
                result = _ask_impl(AskRequest(question=job["question"]), db, request_id=f"retry-{job_id}")
            elif job["operation"] == "related_graph":
                result = get_related_graph(RelatedGraphRequest(question=job["question"], conversation_id=job.get("conversation_id")), db)
            else:
                raise ValueError("不支持的重试操作")
            job["status"] = "succeeded"
            job["result"] = {"answer": result.get("answer"), "answer_quality": result.get("answer_quality"),
                              "candidate_id": result.get("candidate_id"), "knowledge_graph": result.get("knowledge_graph")}
            job["error"] = None
            break
        except Exception as exc:
            job["error"] = str(exc)
            job["status"] = "retrying" if job["attempts"] < job["max_attempts"] else "failed"
        finally:
            db.close()
            job["updated_at"] = _now()
        _persist(job)


def _worker():
    try:
        _, job_id = _pending.get_nowait()
    except Exception:
        return
    try:
        _run(job_id)
    finally:
        _pending.task_done()


def _persist(job):
    db = SessionLocal()
    try:
        stored = db.query(AIRetryJob).filter(AIRetryJob.id == job["id"]).first()
        if stored:
            stored.status = job["status"]
            stored.attempts = job["attempts"]
            stored.error = job["error"]
            stored.result_json = json.dumps(job["result"], ensure_ascii=False) if job["result"] else None
            db.commit()
    finally:
        db.close()


def resume_pending_jobs():
    if os.getenv("MATH_AGENT_DISABLE_RETRY_WORKER", "0").lower() in {"1", "true", "yes"}:
        return
    db = SessionLocal()
    try:
        jobs = db.query(AIRetryJob).filter(AIRetryJob.status.in_(["queued", "running", "retrying"])).all()
        for stored in jobs:
            with _lock:
                _jobs[stored.id] = {"id": stored.id, "operation": stored.operation, "question": stored.question, "conversation_id": stored.conversation_id, "status": "queued", "attempts": stored.attempts, "max_attempts": stored.max_attempts, "error": stored.error, "result": None, "created_at": stored.created_at.isoformat() if stored.created_at else _now(), "updated_at": _now()}
            _pending.put((0, stored.id))
            _executor.submit(_worker)
    finally:
        db.close()


def snapshot():
    with _lock:
        return [job.copy() for job in _jobs.values()]


def queue_stats():
    with _lock:
        counts = {}
        for job in _jobs.values():
            counts[job["status"]] = counts.get(job["status"], 0) + 1
        return counts
