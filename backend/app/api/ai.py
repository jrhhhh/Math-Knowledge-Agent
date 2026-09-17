from __future__ import annotations

import json
import asyncio
import queue
import csv
import io
import hashlib
import re
import os
import hmac
import urllib.request
from uuid import uuid4
import time
import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from openai import (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    APIStatusError,
)

from app.database import SessionLocal
from app.models.concept import Concept
from app.models.concept_relation import ConceptRelation
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept
from app.models.graph_candidate import GraphCandidate
from app.models.concept_alias import ConceptAlias
from app.models.graph_candidate_event import GraphCandidateEvent
from app.models.ai_retry_job import AIRetryJob
from app.models.ai_request_log import AIRequestLog
from app.models.question_sample import QuestionSample
from app.models.answer_record import AnswerRecord, AnswerFeedback
from app.models.answer_review import AnswerReview
from app.models.answer_review_event import AnswerReviewEvent
from app.models.security_event import SecurityEvent
from app.models.ai_task_status import AITaskStatus

from app.ai.analyzer import client, backup_client, backup_model, primary_api_key, primary_base_url, primary_model, primary_timeout
from app.ai.concept_matcher import (
    semantic_retrieve_concepts,
    search_similar_problems,
    normalize_relation,
    find_concept_by_name_or_alias,
    RELATION_PRIORITY,
)
from app.ai.telemetry import record_request, snapshot
from app.ai.retry_queue import enqueue, get_job, queue_stats, cancel_job
from app.ai.local_fallback import local_math_answer
from app.ai.answer_quality import evaluate_answer, quality_retry_instruction
from app.ai.formula_validator import repair_formula
from app.ai.circuit_breaker import before_call, success as circuit_success, failure as circuit_failure, snapshot as circuit_snapshot
from app.security import require_admin, issue_admin_token, login_allowed, record_login_failure, clear_login_failures, record_security_event, alert_delivery_allowed, mark_alert_delivered, _LOCKOUT_SECONDS


router = APIRouter(
    prefix="/ai",
    tags=["AI"]
)

_answer_cache = {}
_ANSWER_CACHE_TTL = 300
_knowledge_version = 0
_cache_metrics = {"hits": 0, "misses": 0}
_stream_results = {}
_STREAM_RESULT_TTL = 600
_task_status = {}
_task_status_lock = threading.Lock()
try:
    REQUEST_BUDGET_SECONDS = max(10.0, float(os.getenv("MATH_AGENT_REQUEST_BUDGET_SECONDS", "85")))
except (TypeError, ValueError):
    REQUEST_BUDGET_SECONDS = 85.0


def remaining_generation_timeout(deadline: float, requested: float) -> float:
    """Return a provider timeout that cannot exceed the request's remaining budget."""
    remaining = deadline - time.perf_counter() - 0.5
    if remaining < 1.0:
        raise TimeoutError("本次问答已达到总时间预算。")
    return min(requested, remaining)


class RequestCancelledError(RuntimeError):
    """Raised at safe boundaries when a streaming client disconnects."""


def check_request_cancelled(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise RequestCancelledError("客户端已断开，已取消本次问答收尾。")


def set_task_status(request_id: str | None, status: str, stage: str, detail: str | None = None, db: Session | None = None, question: str = ""):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not request_id:
        return
    with _task_status_lock:
        _task_status[request_id] = {
            "request_id": request_id,
            "status": status,
            "stage": stage,
            "detail": detail,
            "updated_at": now.isoformat(),
        }
    if db is not None:
        item = db.query(AITaskStatus).filter(AITaskStatus.request_id == request_id).first()
        if item is None:
            item = AITaskStatus(request_id=request_id, question=question, status=status, stage=stage, detail=detail, updated_at=now)
            db.add(item)
        else:
            item.status, item.stage, item.detail, item.updated_at = status, stage, detail, now
        db.commit()


def classify_ai_error(exc):
    if isinstance(exc, (APITimeoutError, TimeoutError)):
        return "timeout", "模型响应超时，请稍后重试。"
    if isinstance(exc, RateLimitError):
        return "rate_limit", "模型请求过于频繁，请稍后重试。"
    if isinstance(exc, APIConnectionError):
        return "network", "无法连接模型服务，请检查网络后重试。"
    if isinstance(exc, APIStatusError):
        return ("server_error", "模型服务暂时异常，请稍后重试。") if exc.status_code >= 500 else ("api_error", "模型服务返回了请求错误。")
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return "invalid_response", "模型返回格式异常，正在等待下一次生成。"
    return "unknown", "模型暂时无法完成回答，请稍后重试。"


def cached_answer(question: str):
    now = time.monotonic()
    for key, value in list(_answer_cache.items()):
        if now - value["at"] >= _ANSWER_CACHE_TTL:
            _answer_cache.pop(key, None)
    entry = _answer_cache.get(question.casefold())
    if entry and entry["version"] == _knowledge_version and time.monotonic() - entry["at"] < _ANSWER_CACHE_TTL:
        _cache_metrics["hits"] += 1
        return entry["value"]
    _cache_metrics["misses"] += 1
    if entry:
        _answer_cache.pop(question.casefold(), None)
    return None


def invalidate_answer_cache():
    global _knowledge_version
    _knowledge_version += 1


def cleanup_stream_results():
    now = time.monotonic()
    for request_id, entry in list(_stream_results.items()):
        if now - entry["at"] >= _STREAM_RESULT_TTL:
            _stream_results.pop(request_id, None)


@router.get("/cache")
def cache_status():
    total = _cache_metrics["hits"] + _cache_metrics["misses"]
    return {"entries": len(_answer_cache), "ttl_seconds": _ANSWER_CACHE_TTL, "knowledge_version": _knowledge_version, "hits": _cache_metrics["hits"], "misses": _cache_metrics["misses"], "hit_rate": round(_cache_metrics["hits"] / total, 4) if total else None}


@router.delete("/cache")
def clear_answer_cache():
    _answer_cache.clear()
    invalidate_answer_cache()
    return {"cleared": True, "entries": 0, "knowledge_version": _knowledge_version}


@router.delete("/cache/{question}")
def invalidate_question_cache(question: str):
    removed = _answer_cache.pop(question.casefold(), None) is not None
    return {"question": question, "removed": removed}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class FeedbackRequest(BaseModel):
    rating: int
    feedback: str | None = None

class AdminLoginRequest(BaseModel):
    key: str

@router.post("/auth/login")
def admin_login(request: AdminLoginRequest, http_request: Request):
    identity = http_request.client.host if http_request.client else "unknown"
    if not login_allowed(identity):
        record_security_event("login_rate_limited", http_request, "too many failures")
        raise HTTPException(status_code=429, detail="登录失败次数过多，请 5 分钟后重试。", headers={"Retry-After": str(_LOCKOUT_SECONDS)})
    configured = os.getenv("MATH_AGENT_ADMIN_KEY", "").strip()
    if not configured or not hmac.compare_digest(request.key, configured):
        record_login_failure(identity)
        record_security_event("login_failed", http_request, "invalid key")
        raise HTTPException(status_code=401, detail="管理员密钥无效。")
    clear_login_failures(identity)
    record_security_event("login_succeeded", http_request)
    return {"access_token": issue_admin_token(configured), "token_type": "bearer", "expires_in": 3600}

@router.get("/security-events")
def security_events(event: str | None = None, ip: str | None = None, limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)):
    query = db.query(SecurityEvent)
    if event: query = query.filter(SecurityEvent.event == event)
    if ip: query = query.filter(SecurityEvent.ip_address == ip)
    items = query.order_by(SecurityEvent.created_at.desc()).limit(limit).all()
    return {"items": [{"id": item.id, "event": item.event, "ip_address": item.ip_address,
                       "path": item.path, "detail": item.detail, "created_at": item.created_at.isoformat()} for item in items], "total": len(items)}

@router.get("/security-alerts")
def security_alerts(db: Session = Depends(get_db)):
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    recent = db.query(SecurityEvent).filter(SecurityEvent.created_at >= cutoff).all()
    counts = {}
    by_ip = {}
    for item in recent:
        counts[item.event] = counts.get(item.event, 0) + 1
        if item.ip_address and item.event in {"login_failed", "login_rate_limited", "admin_denied"}:
            by_ip[item.ip_address] = by_ip.get(item.ip_address, 0) + 1
    alerts = [{"severity": "high", "type": "ip_abuse", "ip_address": ip, "count": count,
               "message": "该 IP 最近 10 分钟出现多次管理安全事件。"} for ip, count in by_ip.items() if count >= 3]
    if counts.get("login_rate_limited", 0):
        alerts.append({"severity": "high", "type": "login_rate_limit", "count": counts["login_rate_limited"], "message": "检测到登录限流事件。"})
    return {"window_minutes": 10, "alert": bool(alerts), "alerts": alerts, "counts": counts}

@router.post("/security-alerts/notify")
def notify_security_alerts(db: Session = Depends(get_db), _: bool = Depends(require_admin)):
    webhook = os.getenv("MATH_AGENT_ALERT_WEBHOOK", "").strip()
    if not webhook:
        raise HTTPException(status_code=503, detail="未配置 MATH_AGENT_ALERT_WEBHOOK。")
    payload = security_alerts(db)
    if not payload["alert"]:
        return {"sent": False, "reason": "no_active_alert", "alerts": []}
    signature = hashlib.sha256(json.dumps(payload["alerts"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    allowed, retry_after = alert_delivery_allowed(signature)
    if not allowed:
        return {"sent": False, "reason": "cooldown", "retry_after": retry_after, "alerts": payload["alerts"]}
    body = json.dumps({"text": "Math Agent 安全告警", **payload}, ensure_ascii=False).encode()
    request = urllib.request.Request(webhook, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status >= 400:
                raise HTTPException(status_code=502, detail="Webhook 返回错误。")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Webhook 发送失败：{exc}") from exc
    mark_alert_delivered(signature)
    return {"sent": True, "alerts": payload["alerts"]}

class ReviewRequest(BaseModel):
    status: str
    note: str | None = None


class EvaluateRequest(BaseModel):
    question: str
    answer: str
    reference_answer: str | None = None
    knowledge_points: list[str] = []


@router.get("/answers")
def list_answers(source: str | None = None, level: str | None = None, offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    query = db.query(AnswerRecord)
    if source:
        query = query.filter(AnswerRecord.answer_source == source)
    if level == "good":
        query = query.filter(AnswerRecord.quality_score >= .75)
    elif level == "partial":
        query = query.filter(AnswerRecord.quality_score >= .5, AnswerRecord.quality_score < .75)
    elif level == "weak":
        query = query.filter(AnswerRecord.quality_score < .5)
    total = query.count()
    items = query.order_by(AnswerRecord.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": [{"id": item.id, "request_id": item.request_id, "question": item.question,
                       "answer_source": item.answer_source, "quality_score": item.quality_score,
                       "duration_seconds": item.duration_seconds, "created_at": item.created_at.isoformat()}
                      for item in items], "total": total, "offset": offset, "limit": limit}


@router.get("/answers/export")
def export_answers(source: str | None = None, level: str | None = None, db: Session = Depends(get_db)):
    data = list_answers(source=source, level=level, offset=0, limit=200, db=db)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "question", "answer_source", "quality_score", "duration_seconds", "created_at"])
    for item in data["items"]:
        writer.writerow([item["id"], item["question"], item["answer_source"], item["quality_score"], item["duration_seconds"], item["created_at"]])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=answer-history.csv"})


@router.get("/answers/stats")
def answer_stats(db: Session = Depends(get_db)):
    records = db.query(AnswerRecord).all()
    feedback = db.query(AnswerFeedback).all()
    by_source = {}
    for item in records:
        bucket = by_source.setdefault(item.answer_source, {"count": 0, "average_quality": 0.0})
        bucket["count"] += 1
        bucket["average_quality"] += item.quality_score or 0.0
    for bucket in by_source.values():
        bucket["average_quality"] = round(bucket["average_quality"] / bucket["count"], 3) if bucket["count"] else 0.0
    return {"total": len(records), "feedback_count": len(feedback),
            "average_rating": round(sum(item.rating for item in feedback) / len(feedback), 2) if feedback else None,
            "by_source": by_source,
            "quality_levels": {"good": sum(1 for item in records if (item.quality_score or 0) >= .75),
                                "partial": sum(1 for item in records if .5 <= (item.quality_score or 0) < .75),
                                "weak": sum(1 for item in records if (item.quality_score or 0) < .5)}}


@router.get("/answers/{answer_id}")
def get_answer(answer_id: int, db: Session = Depends(get_db)):
    item = db.query(AnswerRecord).filter(AnswerRecord.id == answer_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="回答记录不存在。")
    feedback = db.query(AnswerFeedback).filter(AnswerFeedback.answer_id == answer_id).order_by(AnswerFeedback.created_at.desc()).all()
    return {"id": item.id, "request_id": item.request_id, "question": item.question, "answer": item.answer,
            "answer_source": item.answer_source, "quality_score": item.quality_score,
            "duration_seconds": item.duration_seconds, "created_at": item.created_at.isoformat(),
            "feedback": [{"id": entry.id, "rating": entry.rating, "feedback": entry.feedback,
                          "created_at": entry.created_at.isoformat()} for entry in feedback]}


@router.post("/answers/{answer_id}/feedback", status_code=201)
def submit_answer_feedback(answer_id: int, request: FeedbackRequest, db: Session = Depends(get_db)):
    if request.rating not in (1, 2, 3, 4, 5):
        raise HTTPException(status_code=422, detail="rating 必须是 1 到 5。")
    answer = db.query(AnswerRecord).filter(AnswerRecord.id == answer_id).first()
    if answer is None:
        raise HTTPException(status_code=404, detail="回答记录不存在。")
    item = AnswerFeedback(answer_id=answer_id, rating=request.rating, feedback=request.feedback)
    db.add(item)
    if request.rating <= 2 and db.query(AnswerReview).filter(AnswerReview.answer_id == answer_id, AnswerReview.status == "pending").first() is None:
        db.add(AnswerReview(answer_id=answer_id, note="用户评分较低，建议人工核对。"))
    db.commit()
    db.refresh(item)
    return {"id": item.id, "answer_id": item.answer_id, "rating": item.rating, "feedback": item.feedback}


@router.get("/reviews")
def list_answer_reviews(status: str = Query(default="pending"), limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    query = db.query(AnswerReview).order_by(AnswerReview.created_at.desc())
    if status != "all":
        query = query.filter(AnswerReview.status == status)
    items = query.limit(limit).all()
    return {"items": [{"id": item.id, "answer_id": item.answer_id, "status": item.status, "note": item.note,
                       "created_at": item.created_at.isoformat(), "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None}
                      for item in items], "total": len(items)}


@router.post("/answers/{answer_id}/review")
def review_answer(answer_id: int, request: ReviewRequest, db: Session = Depends(get_db), _: bool = Depends(require_admin)):
    if request.status not in {"pending", "fixed", "false_positive"}:
        raise HTTPException(status_code=422, detail="status 必须是 pending、fixed 或 false_positive。")
    if db.query(AnswerRecord).filter(AnswerRecord.id == answer_id).first() is None:
        raise HTTPException(status_code=404, detail="回答记录不存在。")
    item = db.query(AnswerReview).filter(AnswerReview.answer_id == answer_id, AnswerReview.status == "pending").order_by(AnswerReview.id.desc()).first()
    if item is None:
        item = AnswerReview(answer_id=answer_id)
        db.add(item)
    item.status, item.note = request.status, request.note
    item.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None) if request.status != "pending" else None
    db.commit()
    db.refresh(item)
    db.add(AnswerReviewEvent(answer_id=answer_id, review_id=item.id, action=request.status, note=request.note))
    db.commit()
    return {"id": item.id, "answer_id": item.answer_id, "status": item.status, "note": item.note}


@router.get("/answers/{answer_id}/review-events")
def answer_review_events(answer_id: int, db: Session = Depends(get_db)):
    if db.query(AnswerRecord).filter(AnswerRecord.id == answer_id).first() is None:
        raise HTTPException(status_code=404, detail="回答记录不存在。")
    items = db.query(AnswerReviewEvent).filter(AnswerReviewEvent.answer_id == answer_id).order_by(AnswerReviewEvent.created_at.desc()).all()
    return {"items": [{"id": item.id, "review_id": item.review_id, "action": item.action, "note": item.note,
                       "created_at": item.created_at.isoformat()} for item in items], "total": len(items)}


@router.post("/evaluate")
def evaluate_answer_endpoint(request: EvaluateRequest):
    """返回可解释的启发式质量评估；不把启发式分数冒充数学证明器。"""
    quality = evaluate_answer(request.answer, request.question)
    answer_text = request.answer.casefold()
    missing_points = [point for point in request.knowledge_points if point.casefold() not in answer_text]
    reference_coverage = None
    if request.reference_answer:
        reference_terms = [term for term in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", request.reference_answer) if len(term) >= 2]
        reference_coverage = round(sum(term.casefold() in answer_text for term in reference_terms) / len(reference_terms), 2) if reference_terms else 1.0
    warnings = list(quality["formula"]["issues"])
    if missing_points:
        warnings.append("答案未覆盖全部指定知识点。")
    return {
        "score": quality["score"],
        "correctness": quality["score"],
        "completeness": round(max(0.0, quality["score"] - 0.1 * len(missing_points)), 2),
        "formula_valid": quality["formula"]["valid"],
        "logic_valid": bool(quality["checks"].get("has_reasoning") or quality["checks"].get("has_conclusion")),
        "question_type": quality["question_type"],
        "level": quality["level"],
        "checks": quality["checks"],
        "missing_points": missing_points,
        "reference_coverage": reference_coverage,
        "warnings": warnings,
    }


@router.get("/health")
def ai_health():
    """返回 AI 调用计数和最近失败，便于定位 DeepSeek 不稳定。"""
    metrics = snapshot()
    total = metrics["requests"]
    metrics["success_rate"] = round(metrics["successes"] / total, 4) if total else None
    metrics["average_duration_seconds"] = round(metrics.pop("duration_total") / total, 3) if total else None
    samples = metrics.pop("first_token_samples")
    metrics["average_first_token_seconds"] = round(metrics.pop("first_token_total") / samples, 3) if samples else None
    metrics["retry_queue"] = queue_stats()
    metrics["model_circuit"] = circuit_snapshot()
    metrics["primary_model_configured"] = bool(primary_api_key)
    metrics["primary_model"] = primary_model
    metrics["primary_base_url"] = primary_base_url
    metrics["primary_timeout_seconds"] = primary_timeout
    metrics["request_budget_seconds"] = REQUEST_BUDGET_SECONDS
    metrics["backup_model_configured"] = backup_client is not None
    metrics["request_logs_deleted"] = cleanup_request_logs()
    return metrics


@router.get("/tasks")
def list_task_statuses(status: str | None = None, offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    query = db.query(AITaskStatus)
    if status:
        query = query.filter(AITaskStatus.status == status)
    total = query.count()
    items = query.order_by(AITaskStatus.updated_at.desc()).offset(offset).limit(limit).all()
    return {"items": [{"request_id": item.request_id, "question": item.question, "status": item.status,
                        "stage": item.stage, "detail": item.detail,
                        "updated_at": item.updated_at.isoformat() if item.updated_at else None} for item in items],
            "total": total, "offset": offset, "limit": limit}


@router.post("/tasks/cleanup")
def cleanup_task_statuses(older_than_days: int = Query(default=30, ge=1, le=3650), db: Session = Depends(get_db), _: bool = Depends(require_admin)):
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=older_than_days)
    terminal = ("succeeded", "failed", "cancelled")
    deleted = db.query(AITaskStatus).filter(AITaskStatus.status.in_(terminal), AITaskStatus.updated_at < cutoff).delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted, "older_than_days": older_than_days, "cutoff": cutoff.isoformat()}


@router.post("/tasks/{request_id}/retry")
def retry_task(request_id: str, db: Session = Depends(get_db)):
    item = db.query(AITaskStatus).filter(AITaskStatus.request_id == request_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="未找到该问答任务。")
    if item.status not in {"failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="只有失败或取消的任务可以重新执行。")
    job_id = enqueue("answer", item.question, max_attempts=2, priority=8)
    set_task_status(request_id, "queued", "已重新加入重试队列", f"retry_job_id={job_id}", db=db, question=item.question)
    return {"request_id": request_id, "job_id": job_id, "status": "queued"}


@router.get("/tasks/{request_id}")
def task_status(request_id: str, db: Session = Depends(get_db)):
    """Return the live in-process state plus the durable request-log result."""
    with _task_status_lock:
        live = dict(_task_status.get(request_id, {}))
    persisted = db.query(AITaskStatus).filter(AITaskStatus.request_id == request_id).first()
    if persisted:
        live.update({"request_id": persisted.request_id, "status": persisted.status, "stage": persisted.stage,
                     "detail": persisted.detail, "question": persisted.question,
                     "updated_at": persisted.updated_at.isoformat() if persisted.updated_at else live.get("updated_at")})
    log = db.query(AIRequestLog).filter(AIRequestLog.request_id == request_id).order_by(AIRequestLog.id.desc()).first()
    if log:
        live.update({
            "status": log.status,
            "error_code": log.error_code,
            "error_detail": log.error_detail,
            "duration_seconds": log.duration_seconds,
            "updated_at": log.created_at.isoformat() if log.created_at else live.get("updated_at"),
        })
    if not live:
        raise HTTPException(status_code=404, detail="未找到该问答任务。")
    stream_result = _stream_results.get(request_id)
    if stream_result:
        live["result"] = stream_result["value"]
    return live

@router.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics():
    metrics = snapshot()
    backup_status_path = os.getenv("MATH_AGENT_BACKUP_STATUS_FILE", "backups/backup-status.json")
    try:
        with open(backup_status_path, encoding="utf-8") as stream:
            automated_backup = json.load(stream)
    except (OSError, json.JSONDecodeError):
        automated_backup = {"status": "unknown", "timestamp": 0}
    total = metrics["requests"]
    lines = [
        "# HELP math_agent_requests_total Total AI requests.",
        "# TYPE math_agent_requests_total counter",
        f"math_agent_requests_total {metrics['requests']}",
        f"math_agent_requests_succeeded_total {metrics['successes']}",
        f"math_agent_requests_failed_total {metrics['failures']}",
        f"math_agent_retries_total {metrics['retries']}",
        f"math_agent_slow_requests_total {metrics['slow_requests']}",
        f"math_agent_duration_seconds_total {metrics['duration_total']:.6f}",
        f"math_agent_cache_entries {len(_answer_cache)}",
        f"math_agent_cache_hits_total {_cache_metrics['hits']}",
        f"math_agent_cache_misses_total {_cache_metrics['misses']}",
        f"math_agent_backups_succeeded_total {metrics['backups_succeeded']}",
        f"math_agent_backups_failed_total {metrics['backups_failed']}",
        f"math_agent_last_backup_timestamp {metrics['last_backup_timestamp']}",
        f"math_agent_automated_backup_success {1 if automated_backup.get('status') == 'succeeded' else 0}",
        f"math_agent_automated_backup_failure {1 if automated_backup.get('status') == 'failed' else 0}",
        f"math_agent_automated_backup_timestamp {automated_backup.get('timestamp', 0)}",
        f"math_agent_success_ratio {metrics['successes'] / total if total else 0:.6f}",
    ]
    for status, count in queue_stats().items():
        lines.append(f'math_agent_retry_queue_jobs{{status="{status}"}} {count}')
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


def cleanup_request_logs(retention_days: int = 30):
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)
    db = SessionLocal()
    try:
        deleted = db.query(AIRequestLog).filter(AIRequestLog.created_at < cutoff).delete(synchronize_session=False)
        db.commit()
        return deleted
    finally:
        db.close()


def _parse_log_datetime(value: str | None):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"无效的时间格式：{value}，请使用 ISO 8601。") from exc


def _request_log_query(db: Session, status: str | None, since: str | None, until: str | None):
    if status and status not in {"succeeded", "failed"}:
        raise HTTPException(status_code=400, detail="status 只能是 succeeded 或 failed。")
    query = db.query(AIRequestLog)
    if status:
        query = query.filter(AIRequestLog.status == status)
    start, end = _parse_log_datetime(since), _parse_log_datetime(until)
    if start:
        query = query.filter(AIRequestLog.created_at >= start)
    if end:
        query = query.filter(AIRequestLog.created_at <= end)
    return query.order_by(AIRequestLog.created_at.desc())


def _request_log_item(log):
    return {"request_id": log.request_id, "question": log.question, "status": log.status,
            "duration_seconds": log.duration_seconds, "error_code": log.error_code,
            "error_detail": log.error_detail, "created_at": log.created_at.isoformat() if log.created_at else None}


@router.get("/requests")
def list_request_logs(status: str | None = Query(default=None), since: str | None = Query(default=None), until: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)):
    filtered = _request_log_query(db, status, since, until)
    total = filtered.count()
    items = filtered.limit(limit).all()
    return {"items": [_request_log_item(log) for log in items], "total": total, "limit": limit}


@router.get("/requests/export")
def export_request_logs(status: str | None = Query(default=None), since: str | None = Query(default=None), until: str | None = Query(default=None), db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["request_id", "question", "status", "duration_seconds", "error_code", "error_detail", "created_at"])
    writer.writeheader()
    for log in _request_log_query(db, status, since, until).limit(5000).all():
        writer.writerow(_request_log_item(log))
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=ai-request-logs.csv"})


@router.get("/requests/{request_id}")
def get_request_log(request_id: str, db: Session = Depends(get_db)):
    logs = db.query(AIRequestLog).filter(AIRequestLog.request_id == request_id).order_by(AIRequestLog.created_at.desc()).all()
    if not logs:
        raise HTTPException(status_code=404, detail="请求追踪记录不存在。")
    return {"request_id": request_id, "items": [{"status": log.status, "duration_seconds": log.duration_seconds, "error_code": log.error_code, "error_detail": log.error_detail, "created_at": log.created_at.isoformat() if log.created_at else None} for log in logs]}


def log_request_failure(db: Session, request_id: str, question: str, started_at: float, exc):
    code, detail = ("http_error", str(exc.detail)) if isinstance(exc, HTTPException) else classify_ai_error(exc)
    db.add(AIRequestLog(request_id=request_id, question=question, status="failed", duration_seconds=round(time.perf_counter() - started_at, 3), error_code=code, error_detail=detail))
    db.commit()


@router.post("/retry-queue")
def create_retry_job(request: RetryRequest):
    if request.operation not in {"related_graph", "answer"} or not request.question.strip() or request.priority not in {0, 10}:
        raise HTTPException(status_code=422, detail="仅支持对非空问题重试回答或相关知识图谱。")
    return enqueue(request.operation, request.question.strip(), priority=request.priority)


@router.post("/retry-queue/{job_id}/retry")
def retry_failed_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(AIRetryJob).filter(AIRetryJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="重试任务不存在。")
    if job.status not in {"failed", "succeeded"}:
        raise HTTPException(status_code=409, detail="任务仍在处理中，不能重复触发。")
    return enqueue(job.operation, job.question, job.max_attempts, priority=5)


@router.get("/retry-queue/{job_id}")
def retry_job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="重试任务不存在或已过期。")
    return job


@router.post("/retry-queue/{job_id}/cancel")
def cancel_retry_job(job_id: str):
    job = cancel_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="重试任务不存在。")
    return job


@router.get("/retry-queue")
def list_retry_jobs(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    jobs = db.query(AIRetryJob).order_by(AIRetryJob.created_at.desc()).limit(limit).all()
    return {"items": [{"id": job.id, "operation": job.operation, "question": job.question, "status": job.status, "attempts": job.attempts, "max_attempts": job.max_attempts, "error": job.error, "created_at": job.created_at.isoformat() if job.created_at else None, "updated_at": job.updated_at.isoformat() if job.updated_at else None} for job in jobs]}


@router.get("/retry-alerts")
def retry_alerts(window_minutes: int = Query(default=60, ge=1, le=10080), db: Session = Depends(get_db)):
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=window_minutes)
    jobs = db.query(AIRetryJob).filter(AIRetryJob.status == "failed", AIRetryJob.updated_at >= cutoff).order_by(AIRetryJob.updated_at.desc()).limit(20).all()
    return {"window_minutes": window_minutes, "alert": bool(jobs), "failed_count": len(jobs),
            "items": [{"id": job.id, "question": job.question, "attempts": job.attempts,
                       "max_attempts": job.max_attempts, "error": job.error,
                       "updated_at": job.updated_at.isoformat() if job.updated_at else None} for job in jobs]}




class AskRequest(BaseModel):
    question: str


class RelatedGraphRequest(BaseModel):
    question: str


class GraphCandidateUpdateRequest(BaseModel):
    graph: dict


class GraphCandidateBatchRequest(BaseModel):
    candidate_ids: list[int]


class RetryRequest(BaseModel):
    operation: str = "related_graph"
    question: str
    priority: int = 0


def record_candidate_event(db: Session, candidate_id: int, action: str, detail: dict | None = None):
    db.add(GraphCandidateEvent(candidate_id=candidate_id, action=action, detail_json=json.dumps(detail or {}, ensure_ascii=False)))


class ProofAnalyzeRequest(BaseModel):
    question: str
    proof: str


@router.post("/proof-analyze")
def analyze_proof(
    request: ProofAnalyzeRequest,
    db: Session = Depends(get_db),
):
    """分析用户证明的步骤、逻辑缺口和相关知识点。"""
    if not request.question.strip() or not request.proof.strip():
        raise HTTPException(status_code=422, detail="question 和 proof 不能为空。")

    matched = safe_semantic_retrieve_concepts(db, request.question)
    concept_context = [
        {
            "id": item["concept"].id,
            "name": item["concept"].name,
            "type": item["concept"].type,
            "similarity": item.get("similarity", 0.0),
        }
        for item in matched
    ]
    prompt = f"""
你是严格的数学证明审查助手。请分析下面的题目和用户证明。

题目：
{request.question}

用户证明：
{request.proof}

相关知识点候选：
{json.dumps(concept_context, ensure_ascii=False)}

将证明拆成有序步骤，检查每一步是否由前一步和已知条件推出。
错误类型只能使用：missing_assumption、invalid_inference、wrong_theorem、undefined_symbol、circular_reasoning、incomplete、none。
只返回 JSON：
{{
  "valid": true,
  "summary": "总体判断",
  "steps": [
    {{"step": 1, "text": "步骤内容", "status": "valid", "error_type": "none", "reason": "理由", "related_concepts": ["知识点"]}}
  ],
  "missing_assumptions": ["缺失条件"],
  "suggestions": ["改进建议"]
}}
"""
    try:
        raw = call_deepseek(
            messages=[
                {"role": "system", "content": "你是严谨的数学证明验证器，只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            max_retries=2,
            retry_delay=1.0,
            response_format={"type": "json_object"},
        )
        result = json.loads(raw)
    except Exception as exc:
        print("[AI] proof analysis failed:", repr(exc))
        raise HTTPException(status_code=503, detail="证明分析服务暂时不可用。")

    steps = result.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    normalized_steps = []
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            continue
        normalized_steps.append({
            "step": step.get("step", index),
            "text": str(step.get("text", "")),
            "status": step.get("status", "invalid"),
            "error_type": step.get("error_type", "incomplete"),
            "reason": str(step.get("reason", "")),
            "related_concepts": step.get("related_concepts", []),
        })
    return {
        "question": request.question,
        "valid": bool(result.get("valid", False)),
        "summary": str(result.get("summary", "")),
        "steps": normalized_steps,
        "missing_assumptions": result.get("missing_assumptions", []),
        "suggestions": result.get("suggestions", []),
        "matched_concepts": concept_context,
    }


# ============================================================
# DeepSeek API helper
# ============================================================

def call_deepseek(
    messages,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    response_format=None,
    max_tokens: int | None = None,
    timeout: float | None = None,
    extra_body: dict | None = None,
    on_chunk=None,
    circuit_enabled: bool = False,
    provider_client=None,
    model: str = primary_model,
):
    """
    调用 DeepSeek API。

    主要解决：
    - APIConnectionError
    - incomplete chunked read
    - APITimeoutError
    - RateLimitError
    - 部分 5xx 错误

    自动重试。
    """

    last_error = None
    request_started = time.perf_counter()
    first_token_at = None
    attempts = 0

    for attempt in range(max_retries):
        try:
            if circuit_enabled:
                before_call()
            attempts = attempt + 1
            kwargs = {
                "model": model,
                "messages": messages,
            }

            if response_format is not None:
                kwargs["response_format"] = response_format

            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens

            if timeout is not None:
                kwargs["timeout"] = timeout

            if extra_body is not None:
                kwargs["extra_body"] = extra_body
            if on_chunk is not None:
                kwargs["stream"] = True

            response = (provider_client or client).chat.completions.create(**kwargs)
            if on_chunk is not None:
                text_parts = []
                for chunk in response:
                    content = chunk.choices[0].delta.content if chunk.choices and chunk.choices[0].delta else None
                    if content:
                        if first_token_at is None:
                            first_token_at = time.perf_counter()
                        text_parts.append(content)
                        on_chunk(content)
                record_request(True, attempts - 1, duration=time.perf_counter() - request_started, first_token=first_token_at - request_started if first_token_at else None, provider="backup" if provider_client is not None else "primary")
                circuit_success()
                return "".join(text_parts)

            if (
                response.choices
                and response.choices[0].message
                and response.choices[0].message.content
            ):
                record_request(True, attempts - 1, duration=time.perf_counter() - request_started, provider="backup" if provider_client is not None else "primary")
                circuit_success()
                return response.choices[0].message.content

            raise RuntimeError(
                "DeepSeek 返回了空响应。"
            )

        except (
            APIConnectionError,
            APITimeoutError,
            RateLimitError,
        ) as exc:

            last_error = exc
            circuit_failure()

            if attempt < max_retries - 1:
                time.sleep(
                    retry_delay * (attempt + 1)
                )
                continue

            break

        except APIStatusError as exc:

            last_error = exc
            circuit_failure()

            # 只有服务器错误才值得重试
            if exc.status_code >= 500:
                if attempt < max_retries - 1:
                    time.sleep(
                        retry_delay * (attempt + 1)
                    )
                    continue

            break

        except Exception as exc:

            last_error = exc
            circuit_failure()

            # 未知错误不无限重试
            break

    if last_error is not None:
        record_request(False, max(attempts - 1, 0), repr(last_error), duration=time.perf_counter() - request_started, provider="backup" if provider_client is not None else "primary")
        raise last_error

    raise RuntimeError(
        "DeepSeek API 调用失败。"
    )


# ============================================================
# Safe AI retrieval
# ============================================================

def safe_semantic_retrieve_concepts(
    db: Session,
    question: str
):
    """
    知识点语义检索。

    semantic_retrieve_concepts() 当前返回：

    [
        {
            "concept": Concept对象,
            "similarity": 0.95,
            "reason": "..."
        }
    ]

    如果 DeepSeek 暂时不可用，
    不让整个请求直接崩溃。
    """

    # 常见问题优先走本地匹配，避免为明显命中的知识点调用 LLM。
    normalized_question = "".join(question.lower().split())
    local_matches = []
    for concept in db.query(Concept).all():
        normalized_name = "".join((concept.name or "").lower().split())
        if normalized_name and normalized_name in normalized_question:
            local_matches.append({
                "concept": concept,
                "similarity": 1.0,
                "reason": "知识点名称在问题中直接出现。",
            })
    concepts_by_id = {concept.id: concept for concept in db.query(Concept).all()}
    for alias in db.query(ConceptAlias).all():
        normalized_alias = "".join((alias.alias or "").lower().split())
        concept = concepts_by_id.get(alias.concept_id)
        if normalized_alias and normalized_alias in normalized_question and concept is not None:
            local_matches.append({
                "concept": concept,
                "similarity": 0.98,
                "reason": f"通过知识点别名“{alias.alias}”匹配。",
            })
    if local_matches:
        unique_matches = {}
        for item in local_matches:
            concept_id = item["concept"].id
            if concept_id not in unique_matches or item["similarity"] > unique_matches[concept_id]["similarity"]:
                unique_matches[concept_id] = item
        return sorted(unique_matches.values(), key=lambda item: item["similarity"], reverse=True)[:5]

    # 短输入通常是“定理/概念名称”查询。若本地库未收录，直接交给
    # 数学回答模型比先等待一次全库语义检索更快，也不会丢失答案质量。
    if len(normalized_question) <= 20:
        print("[AI] skipping semantic retrieval for short unmatched query")
        return []

    try:
        return semantic_retrieve_concepts(
            db,
            question
        )

    except Exception as exc:
        print(
            "[AI] semantic concept retrieval failed:",
            repr(exc)
        )

        return []


def safe_search_similar_problems(
    db: Session,
    question: str,
    concept_ids: list[int],
):
    """
    历史相似题目检索。

    如果语义排序 API 失败，
    至少返回基于知识点召回的历史题目。
    """

    try:
        return search_similar_problems(
            db=db,
            question=question,
            concept_ids=concept_ids,
            candidate_limit=10,
            result_limit=5,
            semantic=False,
        )

    except Exception as exc:
        print(
            "[AI] similar problem search failed:",
            repr(exc)
        )

        # ----------------------------------------------------
        # 降级策略：
        # 直接根据知识点找历史题目
        # ----------------------------------------------------

        if not concept_ids:
            return []

        problems = (
            db.query(
                Problem,
                ProblemConcept
            )
            .join(
                ProblemConcept,
                Problem.id
                == ProblemConcept.problem_id
            )
            .filter(
                ProblemConcept.concept_id.in_(
                    concept_ids
                )
            )
            .order_by(
                ProblemConcept.importance.desc()
            )
            .limit(5)
            .all()
        )

        results = []

        for problem, relation in problems:

            results.append({
                "id": problem.id,
                "title": problem.title,
                "content": problem.content,
                "solution": problem.solution,
                "difficulty": problem.difficulty,
                "score": relation.importance or 0,
                "similarity": None,
                "reason": "基于相关知识点召回"
            })

        return results


# ============================================================
# Knowledge graph
# ============================================================

def build_knowledge_graph(
    db: Session,
    matched_concepts
):
    """
    根据当前问题匹配到的知识点，
    展开一层知识图谱。

    matched_concepts 的结构：

    [
        {
            "concept": Concept对象,
            "similarity": ...,
            "reason": ...
        }
    ]
    """

    graph_nodes = []
    graph_relations = []

    visited_concepts = set()
    relation_keys = set()

    # --------------------------------------------------------
    # 第一层：直接匹配知识点
    # --------------------------------------------------------

    for item in matched_concepts:

        concept = item["concept"]

        if concept.id in visited_concepts:
            continue

        graph_nodes.append({
            "id": concept.id,
            "name": concept.name,
            "type": concept.type,
            "description": concept.description,
            "field": concept.field,
            "level": concept.level
        })

        visited_concepts.add(
            concept.id
        )

    # --------------------------------------------------------
    # 第二层：展开关系
    # --------------------------------------------------------

    for item in matched_concepts:

        concept = item["concept"]

        relations = (
            db.query(ConceptRelation)
            .filter(
                (
                    (
                        ConceptRelation.source_concept_id
                        == concept.id
                    )
                    |
                    (
                        ConceptRelation.target_concept_id
                        == concept.id
                    )
                )
            )
            .all()
        )

        for relation in relations:

            source = (
                db.query(Concept)
                .filter(
                    Concept.id
                    == relation.source_concept_id
                )
                .first()
            )

            target = (
                db.query(Concept)
                .filter(
                    Concept.id
                    == relation.target_concept_id
                )
                .first()
            )

            if source is None or target is None:
                continue

            relation_key = (
                source.id,
                target.id,
                relation.relation
            )

            if relation_key in relation_keys:
                continue

            relation_keys.add(
                relation_key
            )

            # ----------------------------------------------
            # source node
            # ----------------------------------------------

            if source.id not in visited_concepts:

                graph_nodes.append({
                    "id": source.id,
                    "name": source.name,
                    "type": source.type,
                    "description": source.description,
                    "field": source.field,
                    "level": source.level
                })

                visited_concepts.add(
                    source.id
                )

            # ----------------------------------------------
            # target node
            # ----------------------------------------------

            if target.id not in visited_concepts:

                graph_nodes.append({
                    "id": target.id,
                    "name": target.name,
                    "type": target.type,
                    "description": target.description,
                    "field": target.field,
                    "level": target.level
                })

                visited_concepts.add(
                    target.id
                )

            # ----------------------------------------------
            # relation
            # ----------------------------------------------

            graph_relations.append({
                "source": {
                    "id": source.id,
                    "name": source.name
                },
                "target": {
                    "id": target.id,
                    "name": target.name
                },
                "relation": relation.relation,
                "weight": relation.weight
            })

    return graph_nodes, graph_relations


@router.post("/related-graph")
def get_related_graph(
    request: RelatedGraphRequest,
    db: Session = Depends(get_db),
):
    """快速筛选并展开已有知识库中的一层相关图谱，不调用答案生成模型。"""
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空。")

    cached = (
        db.query(GraphCandidate)
        .filter(GraphCandidate.question == question)
        .order_by(GraphCandidate.created_at.desc())
        .first()
    )
    if cached and cached.created_at and datetime.now(timezone.utc).replace(tzinfo=None) - cached.created_at < timedelta(hours=24):
        graph = json.loads(cached.graph_json)
        return graph_candidate_response(cached, graph, "已复用 24 小时内的 AI 图谱缓存。")

    return generate_ai_related_graph(db, question)


def parse_ai_graph_json(raw: str):
    """解析普通文本通道中可能带有 Markdown 围栏的 JSON 图谱。"""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    return json.loads(text[start:end + 1])


def graph_candidate_response(candidate: GraphCandidate, graph: dict, message: str):
    return {
        "candidate_id": candidate.id,
        "question": candidate.question,
        "concepts": [
            {
                "id": node["id"],
                "name": node["name"],
                "type": node["type"],
                "similarity": 1.0,
                "source": node.get("source", "ai_generated"),
            }
            for node in graph.get("nodes", [])
        ],
        "knowledge_graph": graph,
        "message": message,
    }


def generate_ai_related_graph(db: Session, question: str):
    """由模型生成题目相关的临时知识图谱，并尽可能锚定到本地知识库。"""
    prompt = f"""为数学问题“{question}”生成学习知识图谱。只输出 JSON：
{{"nodes":[{{"id":"n1","name":"名称","type":"concept","description":"说明","field":"分支","level":1}}],"edges":[{{"source":"n1","target":"n2","relation":"prerequisite","weight":0.9}}]}}

给出 4-8 个中文节点和 3-12 条边。type 只能为 concept/theorem/property/method；
relation 只能为 prerequisite/supports/defines/property_of/uses/equivalent_to/generalizes/specializes。
边端点必须存在且不能自环。节点只保留解答该问题必须的定义、条件、定理或方法。"""

    try:
        raw = call_deepseek(
            messages=[
                {
                    "role": "system",
                    "content": "你是严谨的数学知识图谱构建器，只输出合法 JSON。",
                },
                {"role": "user", "content": prompt},
            ],
            max_retries=2,
            max_tokens=1600,
            timeout=45.0,
            # 图谱是结构化抽取任务，不需要消耗高强度推理预算；关闭默认
            # thinking 模式可避免 reasoning_content 挤占 JSON 正文。
            extra_body={"thinking": {"type": "disabled"}},
        )

        generated = parse_ai_graph_json(raw)
    except json.JSONDecodeError:
        # 某些推理轮次会在较长描述字段中截断。第二轮改用极简契约，
        # 仍完全由 AI 生成，只减少令牌与格式风险。
        compact_prompt = f"""为“{question}”输出一个数学知识图谱 JSON，不要解释：
{{"nodes":[{{"id":"n1","name":"概念","type":"concept"}}],"edges":[{{"source":"n1","target":"n2","relation":"uses","weight":0.9}}]}}
给 4-7 个节点和 3-10 条边。type 仅 concept/theorem/property/method；relation 仅 prerequisite/supports/defines/property_of/uses/equivalent_to/generalizes/specializes。"""
        try:
            raw = call_deepseek(
                messages=[
                    {"role": "system", "content": "你是数学知识图谱构建器，只输出完整合法 JSON。"},
                    {"role": "user", "content": compact_prompt},
                ],
                max_retries=2,
                max_tokens=1600,
                timeout=45.0,
                extra_body={"thinking": {"type": "disabled"}},
            )
            generated = parse_ai_graph_json(raw)
        except Exception as exc:
            print("[AI] compact related graph generation failed:", repr(exc))
            raise HTTPException(
                status_code=503,
                detail="DeepSeek 未能生成完整知识图谱，请稍后重试。",
            ) from exc
    except Exception as exc:
        print("[AI] related graph generation failed:", repr(exc))
        raise HTTPException(
            status_code=503,
            detail="DeepSeek 未能生成知识图谱，请稍后重试。",
        ) from exc

    valid_types = {"concept", "theorem", "property", "method"}
    generated_nodes = generated.get("nodes")
    if not isinstance(generated_nodes, list):
        raise HTTPException(status_code=502, detail="DeepSeek 返回的知识图谱格式无效。")

    database_concepts = db.query(Concept).all()
    by_normalized_name = {
        "".join((concept.name or "").lower().split()): concept
        for concept in database_concepts
    }
    by_normalized_name.update({
        "".join((alias.alias or "").lower().split()): concept
        for alias in db.query(ConceptAlias).all()
        for concept in database_concepts
        if concept.id == alias.concept_id
    })
    nodes = []
    node_id_map = {}
    used_ids = set()
    matched_concepts = []

    for index, node in enumerate(generated_nodes[:10], start=1):
        if not isinstance(node, dict):
            continue
        source_id = str(node.get("id", "")).strip()
        name = str(node.get("name", "")).strip()[:48]
        node_type = str(node.get("type", "concept")).strip().lower()
        if not source_id or not name or source_id in node_id_map or node_type not in valid_types:
            continue

        normalized_name = "".join(name.lower().split())
        local_concept = by_normalized_name.get(normalized_name)
        if local_concept is not None:
            graph_id = local_concept.id
            matched_concepts.append({
                "concept": local_concept,
                "similarity": 1.0,
                "reason": "AI 图谱节点与本地知识点同名。",
            })
            node_data = {
                "id": graph_id,
                "name": local_concept.name,
                "type": local_concept.type,
                "description": local_concept.description,
                "field": local_concept.field,
                "level": local_concept.level,
                "source": "knowledge_base",
            }
        else:
            graph_id = f"ai-{index}"
            node_data = {
                "id": graph_id,
                "name": name,
                "type": node_type,
                "description": str(node.get("description", "")).strip()[:160],
                "field": str(node.get("field", "数学")).strip()[:32] or "数学",
                "level": max(1, min(5, int(node.get("level", 1)) if str(node.get("level", "")).isdigit() else 1)),
                "source": "ai_generated",
            }

        if graph_id in used_ids:
            node_id_map[source_id] = graph_id
            continue
        used_ids.add(graph_id)
        node_id_map[source_id] = graph_id
        nodes.append(node_data)

    if len(nodes) < 2:
        raise HTTPException(status_code=502, detail="DeepSeek 未返回足够的有效知识点，请重试。")

    edges = []
    edge_keys = set()
    for edge in generated.get("edges", [])[:14]:
        if not isinstance(edge, dict):
            continue
        source = node_id_map.get(str(edge.get("source", "")).strip())
        target = node_id_map.get(str(edge.get("target", "")).strip())
        relation = normalize_relation(edge.get("relation"))
        if source is None or target is None or source == target or relation is None:
            continue
        edge_key = (source, target, relation)
        if edge_key in edge_keys:
            continue
        edge_keys.add(edge_key)
        try:
            weight = max(0.0, min(1.0, float(edge.get("weight", 0.8))))
        except (TypeError, ValueError):
            weight = 0.8
        edges.append({"source": source, "target": target, "relation": relation, "weight": weight})

    # 已知节点额外展开真实数据库关系，使 AI 结果与既有知识库连通。
    local_nodes, local_relations = build_knowledge_graph(db, matched_concepts)
    known_node_ids = {node["id"] for node in nodes}
    for local_node in local_nodes:
        if local_node["id"] not in known_node_ids and len(nodes) < 16:
            local_node["source"] = "knowledge_base"
            nodes.append(local_node)
            known_node_ids.add(local_node["id"])
    for relation in local_relations:
        edge_key = (relation["source"]["id"], relation["target"]["id"], relation["relation"])
        if edge_key not in edge_keys:
            edge_keys.add(edge_key)
            edges.append({
                "source": relation["source"]["id"],
                "target": relation["target"]["id"],
                "relation": relation["relation"],
                "weight": relation.get("weight", 1.0),
            })

    candidate = GraphCandidate(
        question=question,
        graph_json=json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False),
        validation_json=json.dumps({"valid": True, "invalid_edges": []}, ensure_ascii=False),
        status="pending",
    )
    db.add(candidate)
    db.commit()
    record_candidate_event(db, candidate.id, "generated", {"node_count": len(nodes), "edge_count": len(edges)})
    db.commit()
    db.refresh(candidate)

    return graph_candidate_response(
        candidate,
        {"nodes": nodes, "edges": edges},
        "AI 已根据问题生成相关知识图谱。",
    )


@router.get("/graph-candidates")
def list_graph_candidates(
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """分页查看候选图谱，供审核界面使用。"""
    allowed_statuses = {"pending", "validated", "rejected", "needs_review", "saved"}
    if status is not None and status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="无效的候选图谱状态。")
    query = db.query(GraphCandidate)
    if status is not None:
        query = query.filter(GraphCandidate.status == status)
    total = query.count()
    candidates = query.order_by(GraphCandidate.created_at.desc()).offset(offset).limit(limit).all()
    items = []
    for candidate in candidates:
        graph = json.loads(candidate.graph_json)
        items.append({
            "id": candidate.id,
            "question": candidate.question,
            "status": candidate.status,
            "node_count": len(graph.get("nodes", [])),
            "edge_count": len(graph.get("edges", [])),
            "validation": json.loads(candidate.validation_json or "{}"),
            "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
        })
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/graph-candidates/stats")
def graph_candidate_stats(db: Session = Depends(get_db)):
    """返回候选图谱各审核状态的数量。"""
    rows = db.query(GraphCandidate.status).all()
    counts = {status: 0 for status in {"pending", "validated", "rejected", "needs_review", "saved"}}
    for (status,) in rows:
        counts[status] = counts.get(status, 0) + 1
    return {"total": len(rows), "by_status": counts}


@router.post("/graph-candidates/batch-validate")
def batch_validate_graph_candidates(
    request: GraphCandidateBatchRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    """批量执行候选图谱校验，单条失败不会阻断其余候选。"""
    candidate_ids = list(dict.fromkeys(request.candidate_ids))[:50]
    results = []
    for candidate_id in candidate_ids:
        candidate = db.query(GraphCandidate).filter(GraphCandidate.id == candidate_id).first()
        if candidate is None:
            results.append({"candidate_id": candidate_id, "status": "missing", "error": "候选图谱不存在。"})
            continue
        try:
            result = validate_graph_candidate(candidate_id, db)
            results.append({"candidate_id": candidate_id, "status": result["status"], "validation": result["validation"]})
        except HTTPException as exc:
            results.append({"candidate_id": candidate_id, "status": candidate.status, "error": exc.detail})
    summary = {}
    for result in results:
        summary[result["status"]] = summary.get(result["status"], 0) + 1
    return {"results": results, "summary": summary}


@router.post("/graph-candidates/batch-save-preview")
def batch_save_preview(
    request: GraphCandidateBatchRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    """预览批量保存将新增、替换或跳过的概念和关系。"""
    candidate_ids = list(dict.fromkeys(request.candidate_ids))[:50]
    preview = []
    for candidate_id in candidate_ids:
        candidate = db.query(GraphCandidate).filter(GraphCandidate.id == candidate_id).first()
        if candidate is None:
            preview.append({"candidate_id": candidate_id, "status": "missing"})
            continue
        if candidate.status != "validated":
            preview.append({"candidate_id": candidate_id, "status": "not_validated"})
            continue
        graph = json.loads(candidate.graph_json)
        names = {str(node.get("name", "")).strip() for node in graph.get("nodes", []) if node.get("name")}
        existing_names = {name for (name,) in db.query(Concept.name).filter(Concept.name.in_(names)).all()}
        node_ids = {node.get("id"): node.get("name", "").strip() for node in graph.get("nodes", [])}
        relation_counts = {"new": 0, "replace": 0, "skip": 0}
        for edge in graph.get("edges", []):
            source = db.query(Concept).filter(Concept.name == node_ids.get(edge.get("source"))).first()
            target = db.query(Concept).filter(Concept.name == node_ids.get(edge.get("target"))).first()
            relation = normalize_relation(edge.get("relation"))
            if source is None or target is None or relation is None or source.id == target.id:
                relation_counts["new"] += 1
                continue
            existing = db.query(ConceptRelation).filter_by(source_concept_id=source.id, target_concept_id=target.id).all()
            if not existing:
                relation_counts["new"] += 1
            elif any(normalize_relation(item.relation) == relation for item in existing):
                relation_counts["skip"] += 1
            elif RELATION_PRIORITY.get(relation, 0) > max(RELATION_PRIORITY.get(normalize_relation(item.relation), 0) for item in existing):
                relation_counts["replace"] += 1
            else:
                relation_counts["skip"] += 1
        preview.append({"candidate_id": candidate.id, "status": "validated", "new_concepts": len(names - existing_names), "existing_concepts": len(existing_names), "relations": relation_counts})
    return {"items": preview, "summary": {"candidates": len(preview), "new_concepts": sum(item.get("new_concepts", 0) for item in preview), "new_relations": sum(item.get("relations", {}).get("new", 0) for item in preview)}}


@router.post("/graph-candidates/batch-save")
def batch_save_graph_candidates(
    request: GraphCandidateBatchRequest,
    db: Session = Depends(get_db),
):
    """批量幂等保存已通过校验的候选图谱。"""
    candidate_ids = list(dict.fromkeys(request.candidate_ids))[:50]
    results = []
    for candidate_id in candidate_ids:
        try:
            results.append(save_graph_candidate(candidate_id, db))
        except HTTPException as exc:
            results.append({"candidate_id": candidate_id, "status": "skipped", "error": exc.detail})
    summary = {"created_concepts": sum(item.get("created_concepts", 0) for item in results), "created_relations": sum(item.get("created_relations", 0) for item in results)}
    return {"results": results, "summary": summary}


@router.get("/graph-candidates/{candidate_id}/events")
def get_graph_candidate_events(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(GraphCandidate).filter(GraphCandidate.id == candidate_id).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="候选图谱不存在。")
    events = db.query(GraphCandidateEvent).filter(GraphCandidateEvent.candidate_id == candidate_id).order_by(GraphCandidateEvent.created_at.asc(), GraphCandidateEvent.id.asc()).all()
    return {"candidate_id": candidate_id, "events": [{"id": event.id, "action": event.action, "detail": json.loads(event.detail_json or "{}"), "created_at": event.created_at.isoformat() if event.created_at else None} for event in events]}


@router.get("/graph-candidates/{candidate_id}")
def get_graph_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(GraphCandidate).filter(GraphCandidate.id == candidate_id).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="候选图谱不存在。")
    return {
        "id": candidate.id,
        "question": candidate.question,
        "status": candidate.status,
        "validation": json.loads(candidate.validation_json or "{}"),
        "knowledge_graph": json.loads(candidate.graph_json),
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
    }


@router.put("/graph-candidates/{candidate_id}")
def update_graph_candidate(
    candidate_id: int,
    request: GraphCandidateUpdateRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    """保存审核者对候选图谱的修改，并强制重新校验。"""
    candidate = db.query(GraphCandidate).filter(GraphCandidate.id == candidate_id).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="候选图谱不存在。")
    graph = request.graph
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list) or len(nodes) < 2:
        raise HTTPException(status_code=422, detail="图谱至少需要两个节点和合法的 nodes/edges 数组。")

    node_ids = set()
    clean_nodes = []
    for node in nodes[:16]:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id", "")).strip()
        name = str(node.get("name", "")).strip()[:48]
        node_type = str(node.get("type", "concept")).strip().lower()
        if not node_id or not name or node_id in node_ids or node_type not in {"concept", "theorem", "property", "method"}:
            raise HTTPException(status_code=422, detail="节点 ID、名称或类型不合法。")
        node_ids.add(node_id)
        clean_nodes.append({
            "id": node_id,
            "name": name,
            "type": node_type,
            "description": str(node.get("description", "")).strip()[:160],
            "field": str(node.get("field", "数学")).strip()[:32] or "数学",
            "level": max(1, min(5, int(node.get("level", 1)) if str(node.get("level", "")).isdigit() else 1)),
            "source": node.get("source", "human_review"),
        })
    if len(clean_nodes) < 2:
        raise HTTPException(status_code=422, detail="图谱至少需要两个有效节点。")

    clean_edges = []
    seen_edges = set()
    for edge in edges[:24]:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source", "")).strip()
        target = str(edge.get("target", "")).strip()
        relation = normalize_relation(edge.get("relation"))
        if source not in node_ids or target not in node_ids or source == target or relation is None:
            raise HTTPException(status_code=422, detail="边端点、自环或关系类型不合法。")
        key = (source, target, relation)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        try:
            weight = max(0.0, min(1.0, float(edge.get("weight", 0.8))))
        except (TypeError, ValueError):
            weight = 0.8
        clean_edges.append({"source": source, "target": target, "relation": relation, "weight": weight})

    candidate.graph_json = json.dumps({"nodes": clean_nodes, "edges": clean_edges}, ensure_ascii=False)
    candidate.validation_json = json.dumps({"valid": False, "reason": "图谱已修改，需要重新进行 AI 语义校验。"}, ensure_ascii=False)
    candidate.status = "pending"
    record_candidate_event(db, candidate.id, "edited", {"node_count": len(clean_nodes), "edge_count": len(clean_edges)})
    db.commit()
    return {
        "candidate_id": candidate.id,
        "status": candidate.status,
        "knowledge_graph": json.loads(candidate.graph_json),
        "message": "图谱修改已保存，请重新执行 AI 校验。",
    }


@router.post("/graph-candidates/{candidate_id}/validate")
def validate_graph_candidate(candidate_id: int, db: Session = Depends(get_db), _: bool = Depends(require_admin)):
    candidate = db.query(GraphCandidate).filter(GraphCandidate.id == candidate_id).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="候选图谱不存在。")
    graph = json.loads(candidate.graph_json)
    node_ids = {node.get("id") for node in graph.get("nodes", [])}
    invalid_edges = []
    for index, edge in enumerate(graph.get("edges", [])):
        relation = normalize_relation(edge.get("relation"))
        if edge.get("source") not in node_ids or edge.get("target") not in node_ids:
            invalid_edges.append({"index": index, "reason": "边端点不存在"})
        elif edge.get("source") == edge.get("target") or relation is None:
            invalid_edges.append({"index": index, "reason": "自环或非法关系"})

    validation = {"valid": not invalid_edges and len(graph.get("nodes", [])) >= 2, "invalid_edges": invalid_edges}
    if validation["valid"]:
        try:
            semantic = validate_graph_semantics(graph)
            validation.update({
                "semantic_valid": semantic["valid"],
                "confidence": semantic["confidence"],
                "semantic_issues": semantic["issues"],
            })
            validation["valid"] = validation["valid"] and semantic["valid"] and semantic["confidence"] >= 0.80
            if not validation["valid"]:
                validation["invalid_edges"].extend(semantic["invalid_edges"])
        except Exception as exc:
            print("[AI] graph semantic validation failed:", repr(exc))
            candidate.validation_json = json.dumps({**validation, "semantic_valid": False, "confidence": 0.0, "semantic_issues": ["AI 语义校验未完成，请重试"]}, ensure_ascii=False)
            candidate.status = "needs_review"
            record_candidate_event(db, candidate.id, "validation_failed", {"error": str(exc.detail)})
            db.commit()
            raise HTTPException(status_code=503, detail="AI 数学语义校验暂时不可用，请稍后重试。") from exc

    candidate.validation_json = json.dumps(validation, ensure_ascii=False)
    candidate.status = "validated" if validation["valid"] else "rejected"
    record_candidate_event(db, candidate.id, "validated" if validation["valid"] else "rejected", validation)
    db.commit()
    return {"candidate_id": candidate.id, "status": candidate.status, "validation": validation}


def validate_graph_semantics(graph: dict):
    """批量判断图谱关系的数学方向和含义，返回可审计的校验结果。"""
    nodes = {str(node.get("id")): node.get("name", "") for node in graph.get("nodes", [])}
    edges = [
        {
            "index": index,
            "source": nodes.get(str(edge.get("source")), ""),
            "target": nodes.get(str(edge.get("target")), ""),
            "relation": edge.get("relation"),
        }
        for index, edge in enumerate(graph.get("edges", []))
    ]
    prompt = f"""请校验这张数学知识图谱是否适合学习。只输出 JSON：
{{"valid":true,"confidence":0.9,"issues":[],"invalid_edges":[]}}

节点：{json.dumps(nodes, ensure_ascii=False)}
关系：{json.dumps(edges, ensure_ascii=False)}

检查每条关系的数学含义和方向；不要因表述风格不同而否定正确关系。
confidence 为 0 到 1。invalid_edges 是有问题的边索引及原因，例如 [{{"index":1,"reason":"方向相反"}}]。
只有存在明显数学错误或缺少必要条件时才判 valid=false。"""
    raw = call_deepseek(
        messages=[
            {"role": "system", "content": "你是严格的数学知识图谱审校器，只输出完整合法 JSON。"},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        max_retries=2,
        max_tokens=3000,
        timeout=70.0,
        extra_body={"thinking": {"type": "enabled"}},
    )
    result = parse_ai_graph_json(raw)
    try:
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    invalid_edges = result.get("invalid_edges", [])
    if not isinstance(invalid_edges, list):
        invalid_edges = []
    return {
        "valid": bool(result.get("valid", False)),
        "confidence": confidence,
        "issues": result.get("issues", []) if isinstance(result.get("issues", []), list) else [],
        "invalid_edges": invalid_edges,
    }


@router.post("/graph-candidates/{candidate_id}/save")
def save_graph_candidate(candidate_id: int, db: Session = Depends(get_db), _: bool = Depends(require_admin)):
    candidate = db.query(GraphCandidate).filter(GraphCandidate.id == candidate_id).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="候选图谱不存在。")
    if candidate.status == "saved":
        return {"candidate_id": candidate.id, "status": "saved", "created_concepts": 0, "created_relations": 0}
    validation = json.loads(candidate.validation_json or "{}")
    if candidate.status != "validated" or not validation.get("valid"):
        raise HTTPException(status_code=409, detail="候选图谱尚未通过校验。")

    graph = json.loads(candidate.graph_json)
    id_map = {}
    created_concepts = 0
    for node in graph.get("nodes", []):
        name = str(node.get("name", "")).strip()
        if not name:
            continue
        concept = db.query(Concept).filter(Concept.name == name).first()
        if concept is None:
            concept = Concept(name=name, type=node.get("type", "concept"), description=node.get("description", ""), field=node.get("field", "数学"), level=node.get("level", 1))
            db.add(concept)
            db.flush()
            created_concepts += 1
        id_map[node.get("id")] = concept.id

    created_relations = 0
    relation_conflicts = []
    for edge in graph.get("edges", []):
        source_id, target_id = id_map.get(edge.get("source")), id_map.get(edge.get("target"))
        relation = normalize_relation(edge.get("relation"))
        if source_id is None or target_id is None or relation is None or source_id == target_id:
            continue
        try:
            weight = max(0.0, min(1.0, float(edge.get("weight", 0.8))))
        except (TypeError, ValueError):
            weight = 0.8
        existing_relations = db.query(ConceptRelation).filter_by(source_concept_id=source_id, target_concept_id=target_id).all()
        same_relation = next((item for item in existing_relations if normalize_relation(item.relation) == relation), None)
        if same_relation is not None:
            same_relation.weight = max(float(same_relation.weight or 0.0), weight)
            continue
        new_priority = RELATION_PRIORITY.get(relation, 0)
        old_priorities = [RELATION_PRIORITY.get(normalize_relation(item.relation), 0) for item in existing_relations]
        if old_priorities and new_priority <= max(old_priorities):
            relation_conflicts.append({"source": source_id, "target": target_id, "new_relation": relation, "old_relations": [item.relation for item in existing_relations], "action": "skipped", "new_priority": new_priority, "old_priority": max(old_priorities)})
            continue
        if old_priorities:
            relation_conflicts.append({"source": source_id, "target": target_id, "new_relation": relation, "old_relations": [item.relation for item in existing_relations], "action": "replaced", "new_priority": new_priority, "old_priority": max(old_priorities)})
        for existing in existing_relations:
            db.delete(existing)
        db.add(ConceptRelation(source_concept_id=source_id, target_concept_id=target_id, relation=relation, weight=weight))
        created_relations += 1
    candidate.status = "saved"
    for conflict in relation_conflicts:
        record_candidate_event(db, candidate.id, "relation_conflict", conflict)
    record_candidate_event(db, candidate.id, "saved", {"created_concepts": created_concepts, "created_relations": created_relations, "relation_conflicts": len(relation_conflicts)})
    db.commit()
    invalidate_answer_cache()
    return {"candidate_id": candidate.id, "status": candidate.status, "created_concepts": created_concepts, "created_relations": created_relations}


# ============================================================
# Historical problems
# ============================================================

def get_historical_problems(
    db: Session,
    matched_concepts,
    limit: int = 10
):
    """
    根据知识点召回历史题目。

    一个题目可能关联多个知识点。
    """

    historical_problems = {}
    total_matched_concepts = len({item["concept"].id for item in matched_concepts})
    similarity_by_concept = {}
    for item in matched_concepts:
        try:
            similarity = float(item.get("similarity") or 0.0)
        except (TypeError, ValueError):
            similarity = 0.0
        similarity_by_concept[item["concept"].id] = max(0.0, min(1.0, similarity))

    for item in matched_concepts:

        concept = item["concept"]

        problem_relations = (
            db.query(ProblemConcept)
            .filter(
                ProblemConcept.concept_id
                == concept.id
            )
            .all()
        )

        for relation in problem_relations:

            problem = (
                db.query(Problem)
                .filter(
                    Problem.id
                    == relation.problem_id
                )
                .first()
            )

            if problem is None:
                continue

            importance = (
                relation.importance
                if relation.importance is not None
                else 0
            )

            if problem.id not in historical_problems:

                historical_problems[
                    problem.id
                ] = {
                    "id": problem.id,
                    "title": problem.title,
                    "content": problem.content,
                    "solution": problem.solution,
                    "difficulty": problem.difficulty,
                    "importance": importance,
                    "matched_concepts": []
                }

            else:

                # 一个题目如果关联多个知识点，
                # 使用最高的重要程度

                historical_problems[
                    problem.id
                ]["importance"] = max(
                    historical_problems[
                        problem.id
                    ]["importance"],
                    importance
                )

            matches = historical_problems[problem.id]["matched_concepts"]
            existing = next(
                (match for match in matches if match["concept_id"] == concept.id),
                None,
            )
            if existing is None:
                matches.append({
                    "concept_id": concept.id,
                    "concept_name": concept.name,
                    "importance": importance,
                    "similarity": similarity_by_concept.get(concept.id, 0.0),
                })
            else:
                existing["importance"] = max(existing["importance"], importance)

    for problem in historical_problems.values():
        matches = problem["matched_concepts"]
        matched_count = len(matches)
        coverage = matched_count / total_matched_concepts if total_matched_concepts else 0.0
        similarities = [match["similarity"] for match in matches]
        problem["coverage"] = round(coverage, 4)
        problem["score"] = round(
            max(similarities, default=0.0) * 0.45
            + coverage * 0.30
            + problem["importance"] * 0.15
            + (sum(similarities) / len(similarities) if similarities else 0.0) * 0.10,
            4,
        )

    # --------------------------------------------------------
    # 按综合相关程度排序
    # --------------------------------------------------------

    problems = sorted(
        historical_problems.values(),
        key=lambda item: (item["score"], item["importance"], item["id"]),
        reverse=True
    )

    return problems[:limit]


# ============================================================
# Format historical problems
# ============================================================

def format_historical_problems(
    problems,
    max_items: int = 8,
    max_content_length: int = 1500,
    max_solution_length: int = 2500,
):
    """
    将历史题目压缩成 Prompt。

    防止历史数据过多导致：
    - Prompt 太长
    - API 响应慢
    - connection closed
    """

    if not problems:
        return "暂无相关历史题目。"

    text_parts = []

    for problem in problems[:max_items]:

        content = problem.get(
            "content"
        ) or ""

        solution = problem.get(
            "solution"
        ) or ""

        content = content[
            :max_content_length
        ]

        solution = solution[
            :max_solution_length
        ]

        matched_names = ", ".join(
            item["concept_name"]
            for item in problem.get(
                "matched_concepts",
                []
            )
        )

        text_parts.append(
            f"""
题目 ID：
{problem["id"]}

题目：
{problem["title"]}

题目内容：
{content}

已有解答：
{solution}

难度：
{problem["difficulty"]}

知识点重要程度：
{problem["importance"]}

相关知识点：
{matched_names}

------------------------------
"""
        )

    return "\n".join(
        text_parts
    )


# ============================================================
# Format similar problems
# ============================================================

def format_similar_problems(
    problems,
    max_items: int = 5,
    max_content_length: int = 1500,
    max_solution_length: int = 2500,
):
    """
    将相似题目压缩成 Prompt。
    """

    if not problems:
        return "暂无高度相似的历史题目。"

    text_parts = []

    for problem in problems[:max_items]:

        content = (
            problem.get("content")
            or ""
        )

        solution = (
            problem.get("solution")
            or ""
        )

        content = content[
            :max_content_length
        ]

        solution = solution[
            :max_solution_length
        ]

        text_parts.append(
            f"""
历史相似题 ID：
{problem["id"]}

题目：
{problem["title"]}

题目内容：
{content}

已有解答：
{solution}

难度：
{problem.get("difficulty")}

知识点召回分数：
{problem.get("score")}

语义相似度：
{problem.get("similarity")}

相似原因：
{problem.get("reason")}

------------------------------
"""
        )

    return "\n".join(
        text_parts
    )


# ============================================================
# Format graph
# ============================================================

def format_graph_nodes(
    graph_nodes
):
    if not graph_nodes:
        return "暂无相关知识图谱信息。"

    text_parts = []

    for node in graph_nodes:

        text_parts.append(
            f"""
知识点：
{node["name"]}

类型：
{node["type"]}

描述：
{node["description"]}

领域：
{node["field"]}

层级：
{node["level"]}

"""
        )

    return "\n".join(
        text_parts
    )


def format_graph_relations(
    graph_relations
):
    if not graph_relations:
        return "暂无相关知识关系。"

    text_parts = []

    for relation in graph_relations:

        text_parts.append(
            f"""
{relation["source"]["name"]}
   -- {relation["relation"]} -->
{relation["target"]["name"]}

权重：
{relation["weight"]}

"""
        )

    return "\n".join(
        text_parts
    )


# ============================================================
# Main AI endpoint
# ============================================================

def _ask_impl(
    request: AskRequest,
    db: Session = Depends(get_db),
    stream_callback=None,
    request_id: str | None = None,
    cancel_event=None,
):
    started_at = time.perf_counter()
    deadline = started_at + REQUEST_BUDGET_SECONDS
    degradation = []
    question = request.question.strip()
    set_task_status(request_id, "queued", "准备问答", db=db, question=question)
    check_request_cancelled(cancel_event)

    if not question:
        raise HTTPException(
            status_code=400,
            detail="问题不能为空。"
        )

    db.add(QuestionSample(question_hash=hashlib.sha256(question.encode("utf-8")).hexdigest(), question_length=len(question), source="ask"))
    db.commit()

    cached = cached_answer(question)
    if cached is not None:
        cached = dict(cached)
        cached["request_id"] = request_id
        cached["cache_hit"] = True
        set_task_status(request_id, "succeeded", "缓存命中", db=db, question=question)
        return cached

    # ========================================================
    # 1. 语义检索知识点
    # ========================================================

    matched_concepts = (
        safe_semantic_retrieve_concepts(
            db,
            question
        )
    )
    set_task_status(request_id, "retrieving", "检索知识点", db=db, question=question)
    check_request_cancelled(cancel_event)
    print("[Timing] concept retrieval: %.2fs" % (time.perf_counter() - started_at))

    # --------------------------------------------------------
    # semantic_retrieve_concepts() 返回的是：
    #
    # {
    #     "concept": Concept,
    #     "similarity": ...,
    #     "reason": ...
    # }
    #
    # 因此这里必须取 item["concept"].id
    # --------------------------------------------------------

    concept_ids = [
        item["concept"].id
        for item in matched_concepts
    ]

    # ========================================================
    # 2. 历史题目召回
    # ========================================================

    historical_problems = (
        get_historical_problems(
            db=db,
            matched_concepts=matched_concepts,
            limit=10
        )
    )
    set_task_status(request_id, "retrieving", "召回历史题目", db=db, question=question)
    check_request_cancelled(cancel_event)
    print("[Timing] historical retrieval: %.2fs" % (time.perf_counter() - started_at))

    # ========================================================
    # 3. 历史相似题目
    # ========================================================

    similar_problems = (
        safe_search_similar_problems(
            db=db,
            question=question,
            concept_ids=concept_ids
        )
    )
    set_task_status(request_id, "retrieving", "检索相似题目", db=db, question=question)
    check_request_cancelled(cancel_event)
    print("[Timing] similar problems: %.2fs" % (time.perf_counter() - started_at))

    # ========================================================
    # 4. 构建知识图谱
    # ========================================================

    (
        graph_nodes,
        graph_relations
    ) = build_knowledge_graph(
        db,
        matched_concepts
    )
    set_task_status(request_id, "generating", "构建知识图谱", db=db, question=question)
    check_request_cancelled(cancel_event)
    print("[Timing] graph build: %.2fs" % (time.perf_counter() - started_at))

    # ========================================================
    # 5. 格式化 Prompt 数据
    # ========================================================

    graph_text = format_graph_nodes(
        graph_nodes
    )

    relation_text = format_graph_relations(
        graph_relations
    )

    historical_problem_text = (
        format_historical_problems(
            historical_problems
        )
    )

    similar_problem_text = (
        format_similar_problems(
            similar_problems
        )
    )

    # ========================================================
    # 6. 最终数学回答 Prompt
    # ========================================================

    prompt = f"""
你是一名专业的数学知识助手。

你的任务是回答用户提出的数学问题。

============================================================
用户问题
============================================================

{question}

============================================================
一、当前问题相关知识点
============================================================

{graph_text}

============================================================
二、知识点之间的关系
============================================================

{relation_text}

============================================================
三、历史题目与已有解答
============================================================

{historical_problem_text}

============================================================
四、历史相似题目
============================================================

{similar_problem_text}

============================================================
回答要求
============================================================

1. 首先直接回答用户的问题。

2. 如果用户要求证明，
   必须给出完整、严谨的数学证明。

3. 可以参考历史题目和已有解答，
   但必须根据当前问题重新进行数学推导。

4. 不要机械复制历史题目的答案。

5. 历史解答只是参考资料。
   如果历史解答存在错误、不完整或不严谨，
   必须根据严格的数学推理进行修正。

6. 如果历史题目与当前问题高度相似，
   可以借鉴其证明思路，
   但必须根据当前问题重新组织答案。

7. 不要声称自己做过不存在的历史题目。

8. 不要创造数据库中不存在的历史题目、
   历史解答或知识点。

9. 如果使用知识图谱中的定理、性质或方法，
   可以自然地解释它们在当前问题中的作用。

10. 数学证明应优先使用定义、定理和严格的逻辑推导。

11. 对于拓扑学问题，
    特别注意区分：

    - 集合
    - 拓扑空间
    - 映射
    - 像
    - 原像
    - 开集
    - 开覆盖
    - 有限子覆盖
    - 紧性
    - 紧集

12. 不要为了使用知识图谱而强行加入无关知识。

13. 如果当前问题和历史题目高度相似，
    可以指出两者之间的联系，
    但不要虚构用户曾经做过某道题。

14. 回答应当具有数学教材级别的严谨性，
    同时尽量让学生能够理解证明为什么成立。

15. 如果问题存在数学上的歧义，
    应先说明采用的定义或解释。

16. 历史题目和相似题目只是辅助材料，
    不能把它们当作数学事实。

17. 如果知识图谱中的关系与严格数学推理冲突，
    以严格数学推理为准。

18. 如果当前问题可以由某个定理直接解决，
    应明确指出所使用的定理。

19. 如果给出证明，
    应尽量按照：

    定义
    → 已知条件
    → 关键定理
    → 推导
    → 结论

    的结构组织。

20. 不要输出与问题无关的大段知识背景。

请直接用中文回答。
"""

    # 最终回答只带入高价值上下文，避免大 Prompt 导致生成超时。
    compact_prompt = f"""请用中文回答这个数学问题：

{question}

相关知识点：
{format_graph_nodes(graph_nodes[:6])}

关键关系：
{format_graph_relations(graph_relations[:10])}

可参考历史题：
{format_historical_problems(historical_problems, max_items=2, max_content_length=400, max_solution_length=600)}

要求：先给结论；证明题按“定义—关键依据—推导—结论”写出简洁且严谨的证明；只使用与当前问题相关的信息；总长度控制在 800 个中文字符以内。"""

    direct_math_prompt = f"""请完整而简洁地回答数学问题：{question}

如果这是一个定理或概念，请依次给出：
1. 准确的定义或定理陈述；
2. 所需条件；
3. 结论及关键公式；
4. 简短证明思路或一个典型应用。

请直接给出数学内容，不要提及知识库、系统或无法回答。"""
    primary_prompt = compact_prompt if matched_concepts else direct_math_prompt
    primary_timeout = 25.0 if matched_concepts else 70.0
    primary_max_tokens = 900 if matched_concepts else 1600

    # ========================================================
    # 7. 最终 DeepSeek 调用
    # ========================================================

    answer_source = "deepseek"
    try:

        answer = call_deepseek(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一名专业、严谨的数学知识助手，"
                        "擅长数学证明、数学知识图谱、"
                        "历史题目检索和数学题目分析。"
                    )
                },
                {
                    "role": "user",
                    "content": primary_prompt
                }
            ],
            max_retries=1,
            max_tokens=primary_max_tokens,
            timeout=remaining_generation_timeout(deadline, primary_timeout),
            on_chunk=stream_callback,
            circuit_enabled=True,
            extra_body={"thinking": {"type": "disabled"}} if stream_callback else None,
        )
        print("[Timing] final answer: %.2fs" % (time.perf_counter() - started_at))

    except Exception as exc:

        print(
            "[AI] final answer generation failed:",
            repr(exc)
        )
        degradation.append("primary_failed")
        set_task_status(request_id, "degraded", "主模型失败，执行降级", repr(exc), db=db, question=question)

        # 若配置了备用 OpenAI 兼容服务，先切换供应商，避免再次消耗主服务超时。
        if backup_client is not None:
            try:
                answer = call_deepseek(
                    messages=[{"role": "system", "content": "你是一名严谨的中文数学教师，直接给出可靠答案。"}, {"role": "user", "content": question}],
                    max_retries=1, max_tokens=primary_max_tokens, timeout=remaining_generation_timeout(deadline, 30.0),
                    on_chunk=stream_callback,
                    extra_body={"thinking": {"type": "disabled"}} if stream_callback else None,
                    provider_client=backup_client, model=backup_model,
                )
                answer_source = "backup_model"
                degradation.append("backup_model")
                set_task_status(request_id, "generating", "备用模型生成", db=db, question=question)
                print("[AI] backup model answered")
            except Exception as backup_exc:
                print("[AI] backup model failed:", repr(backup_exc))
                answer = None
        else:
            answer = None

        # 第一轮使用图谱上下文；若模型返回空内容或超时，改用更长时限的
        # 纯数学回答请求，避免无关的知识库兜底替代真正答案。
        if not answer:
          try:
            answer = call_deepseek(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一名严谨的中文数学教师。直接回答问题；"
                            "若问题是定理，给出定理陈述、条件和证明思路或完整证明。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"请认真回答以下数学问题，不要提及知识库或系统状态：\n\n{question}"
                        ),
                    },
                ],
                max_retries=1,
                max_tokens=1600,
                timeout=remaining_generation_timeout(deadline, 70.0),
                on_chunk=stream_callback,
                circuit_enabled=True,
                extra_body={"thinking": {"type": "disabled"}} if stream_callback else None,
            )
            answer_source = "deepseek_extended"
            degradation.append("extended_primary")
            set_task_status(request_id, "generating", "延长生成", db=db, question=question)
            print("[Timing] extended answer: %.2fs" % (time.perf_counter() - started_at))
          except Exception as retry_exc:
            print("[AI] extended answer generation failed:", repr(retry_exc))
            answer = local_math_answer(question, db)
            answer_source = "local_fallback"
            degradation.append("local_fallback")
            set_task_status(request_id, "degraded", "本地数学兜底", db=db, question=question)
            print("[AI] using deterministic local fallback")

    # ========================================================
    # 8. 返回完整结果
    # ========================================================

    # 非流式请求允许在展示前做一次质量修复；流式响应已经发送过 token，不能重复推送。
    answer, formula_fixes = repair_formula(answer)
    check_request_cancelled(cancel_event)
    initial_quality = evaluate_answer(answer, question)
    if stream_callback is None and answer_source in {"deepseek", "deepseek_extended", "backup_model"} and initial_quality["score"] < 0.5:
        try:
            repaired = call_deepseek(
                messages=[
                    {"role": "system", "content": "你是严谨的中文数学教师。必须写出结论、全部条件、关键推导和最终结论；不要讨论系统状态。"},
                    {"role": "user", "content": f"请修正并完整回答：{question}\n{quality_retry_instruction(initial_quality)}\n\n原回答：{answer}"},
                ],
                max_retries=1, max_tokens=1800, timeout=remaining_generation_timeout(deadline, 70.0), circuit_enabled=True,
            )
            repaired_quality = evaluate_answer(repaired, question)
            if repaired_quality["score"] >= initial_quality["score"]:
                answer, answer_source = repaired, "quality_retry"
                print("[AI] quality retry improved answer")
        except Exception as quality_exc:
            print("[AI] quality retry skipped:", repr(quality_exc))

    print("[Timing] request=%s total ask: %.2fs" % (request_id, time.perf_counter() - started_at))
    result = {
        "request_id": request_id,
        "question": question,

        "answer": answer,
        "answer_source": answer_source,
        "answer_quality": evaluate_answer(answer, question),
        "formula_fixes": formula_fixes,
        "generation_budget_seconds": REQUEST_BUDGET_SECONDS,
        "generation_elapsed_seconds": round(time.perf_counter() - started_at, 3),
        "degradation": degradation,

        "concepts": [
            {
                "id": item["concept"].id,
                "name": item["concept"].name,
                "type": item["concept"].type,
                "similarity": item.get("similarity"),
                "reason": item.get("reason", "")
            }
            for item in matched_concepts
        ],

        "historical_problems": [
            {
                "id": problem["id"],
                "title": problem["title"],
                "content": problem["content"],
                "solution": problem["solution"],
                "difficulty": problem["difficulty"],
                "importance": problem["importance"],
                "matched_concepts": (
                    problem["matched_concepts"]
                ),
                "score": problem.get("score", 0.0),
                "coverage": problem.get("coverage", 0.0)
            }
            for problem in historical_problems
        ],

        "similar_problems": similar_problems,

        "knowledge_graph": {
            "nodes": graph_nodes,
            "relations": graph_relations
        }
    }
    result["cache_hit"] = False
    _answer_cache[question.casefold()] = {"at": time.monotonic(), "version": _knowledge_version, "value": result}
    quality = result["answer_quality"]
    if quality.get("score", 1.0) < 0.75 and not (request_id or "").startswith("retry-"):
        result["quality_retry_job"] = enqueue("answer", question, max_attempts=2, priority=5)
    answer_record = AnswerRecord(request_id=request_id or "unknown", question=question, answer=answer,
                                 answer_source=answer_source, quality_score=quality.get("score"),
                                 duration_seconds=round(time.perf_counter() - started_at, 3))
    db.add(answer_record)
    check_request_cancelled(cancel_event)
    db.flush()
    if (quality.get("score") or 0.0) < 0.5:
        db.add(AnswerReview(answer_id=answer_record.id, note="自动质量评估为低质量，建议人工核对。"))
    db.add(AIRequestLog(request_id=request_id or "unknown", question=question, status="succeeded", duration_seconds=round(time.perf_counter() - started_at, 3)))
    db.commit()
    db.refresh(answer_record)
    result["answer_id"] = answer_record.id
    set_task_status(request_id, "succeeded", "回答完成", db=db, question=question)
    return result


@router.post("/ask")
def ask(request: AskRequest, db: Session = Depends(get_db)):
    request_id = uuid4().hex[:12]
    started_at = time.perf_counter()
    try:
        return _ask_impl(request, db, request_id=request_id)
    except Exception as exc:
        set_task_status(request_id, "failed", "问答失败", str(exc))
        log_request_failure(db, request_id, request.question.strip(), started_at, exc)
        raise


@router.post("/ask-stream")
async def ask_stream(request: AskRequest, request_id: str | None = None):
    """以 SSE 发送阶段进度，最后发送与 /ask 相同的完整结果。"""
    async def events():
        trace_id = request_id or uuid4().hex[:12]
        started_at = time.perf_counter()
        sequence = 0
        def emit(event, payload):
            nonlocal sequence
            sequence += 1
            return f"id: {sequence}\nevent: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        cleanup_stream_results()
        if request_id and request_id in _stream_results:
            yield emit("result", _stream_results[request_id]["value"])
            return
        yield emit("progress", {"stage": "检索知识点"})
        chunks = queue.Queue()
        cancel_event = threading.Event()
        task = None
        try:
            db = SessionLocal()
            task = asyncio.create_task(asyncio.to_thread(_ask_impl, request, db, stream_callback=chunks.put, request_id=trace_id, cancel_event=cancel_event))
            yield emit("progress", {"stage": "召回历史题目"})
            yield emit("progress", {"stage": "生成数学解答"})
            while not task.done():
                while not chunks.empty():
                    yield emit("token", {"text": chunks.get_nowait()})
                await asyncio.sleep(0.1)
            while not chunks.empty():
                yield emit("token", {"text": chunks.get_nowait()})
            result = await task
            if not result.get("answer", "").strip():
                result = await asyncio.to_thread(_ask_impl, request, db)
            if request_id:
                _stream_results[request_id] = {"at": time.monotonic(), "value": result}
            yield emit("result", result)
        except Exception as exc:
            if isinstance(exc, RequestCancelledError):
                set_task_status(trace_id, "cancelled", "客户端已断开", str(exc), db=db if 'db' in locals() else None, question=request.question.strip())
            else:
                set_task_status(trace_id, "failed", "问答失败", str(exc), db=db if 'db' in locals() else None, question=request.question.strip())
            if isinstance(exc, HTTPException):
                code, detail = "http_error", str(exc.detail)
            else:
                code, detail = classify_ai_error(exc)
            if 'db' in locals():
                log_request_failure(db, trace_id, request.question.strip(), started_at, exc)
            yield emit("error", {"error_code": code, "detail": detail})
        finally:
            cancel_event.set()
            if task is None or task.done():
                if 'db' in locals():
                    db.close()
            elif 'db' in locals():
                async def close_after_task():
                    try:
                        await asyncio.shield(task)
                    except BaseException:
                        pass
                    finally:
                        db.close()
                asyncio.create_task(close_after_task())
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
