import json
import re
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.ai import get_db
from app.models.local_template import LocalTemplate
from app.models.local_template_event import LocalTemplateEvent
from app.models.question_sample import QuestionSample
from app.models.template_audit_log import TemplateAuditLog

router = APIRouter(prefix="/local-templates", tags=["Local answer templates"])


class TemplateRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=100)
    pattern: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=20000)
    enabled: bool = True


class TemplateUpdate(BaseModel):
    pattern: str | None = Field(default=None, min_length=1, max_length=500)
    answer: str | None = Field(default=None, min_length=1, max_length=20000)
    enabled: bool | None = None


class TemplatePreview(BaseModel):
    question: str = Field(min_length=1)
    template_id: str | None = None

class TemplateImport(BaseModel):
    items: list[TemplateRequest] = Field(min_length=1, max_length=500)

class TemplateABTest(BaseModel):
    template_ids: list[str] = Field(min_length=2, max_length=2)
    questions: list[str] = Field(min_length=1, max_length=1000)


def serialize(item):
    return {"id": item.id, "template_id": item.template_id, "pattern": item.pattern, "answer": item.answer, "enabled": item.enabled, "review_status": item.review_status, "hit_count": item.hit_count, "last_hit_at": item.last_hit_at.isoformat() if item.last_hit_at else None, "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat()}

@router.get("/usage")
def template_usage(db: Session = Depends(get_db)):
    items = db.query(LocalTemplate).order_by(LocalTemplate.hit_count.desc(), LocalTemplate.id.asc()).all()
    return {"total_hits": sum(item.hit_count for item in items), "items": [{"template_id": item.template_id, "hit_count": item.hit_count, "last_hit_at": item.last_hit_at.isoformat() if item.last_hit_at else None} for item in items]}


@router.get("/recommendations")
def template_recommendations(db: Session = Depends(get_db)):
    items = db.query(LocalTemplate).all()
    recommendations = []
    for item in items:
        if item.review_status == "rejected":
            recommendations.append({"template_id": item.template_id, "reason": "模板已驳回，请修订后重新审核。"})
        elif not item.enabled:
            recommendations.append({"template_id": item.template_id, "reason": "模板已禁用，请确认是否仍需保留。"})
        elif item.review_status == "approved" and item.hit_count == 0:
            recommendations.append({"template_id": item.template_id, "reason": "尚未命中，建议用典型问题测试正则。"})
    return {"items": recommendations, "total": len(recommendations)}


@router.get("/samples/stats")
def sample_stats(db: Session = Depends(get_db)):
    samples = db.query(QuestionSample).all()
    by_template = {}
    for sample in samples:
        key = sample.matched_template_id or "unmatched"
        by_template[key] = by_template.get(key, 0) + 1
    return {"total": len(samples), "matched": len(samples) - by_template.get("unmatched", 0), "by_template": by_template}


@router.get("/samples/recommendations")
def sample_recommendations(db: Session = Depends(get_db)):
    samples = db.query(QuestionSample).filter(QuestionSample.matched_template_id.is_(None)).all()
    buckets = {"short": 0, "medium": 0, "long": 0}
    for sample in samples:
        bucket = "short" if sample.question_length < 12 else ("medium" if sample.question_length < 40 else "long")
        buckets[bucket] += 1
    return {"unmatched": len(samples), "length_buckets": buckets, "recommendation": "收集更多未命中问题后，人工归纳主题并创建模板。" if samples else "暂无需要补充的模板。"}


@router.get("/audit-log")
def audit_log(db: Session = Depends(get_db)):
    items = db.query(TemplateAuditLog).order_by(TemplateAuditLog.created_at.desc()).limit(200).all()
    return {"items": [{"id": item.id, "action": item.action, "detail": item.detail, "created_at": item.created_at.isoformat()} for item in items], "total": len(items)}


@router.delete("/samples")
def cleanup_samples(retention_days: int = Query(default=90, ge=1, le=3650), db: Session = Depends(get_db)):
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)
    deleted = db.query(QuestionSample).filter(QuestionSample.created_at < cutoff).delete(synchronize_session=False)
    db.commit()
    admin_audit(db, "sample_cleanup", f"deleted={deleted},retention_days={retention_days}"); db.commit()
    return {"deleted": deleted, "retention_days": retention_days, "cutoff": cutoff.isoformat()}


@router.post("/ab-test")
def template_ab_test(request: TemplateABTest, db: Session = Depends(get_db)):
    templates = {item.template_id: item for item in db.query(LocalTemplate).filter(LocalTemplate.template_id.in_(request.template_ids), LocalTemplate.enabled.is_(True), LocalTemplate.review_status == "approved").all()}
    if len(templates) != 2:
        raise HTTPException(status_code=404, detail="两个模板都必须存在、启用且已通过审核。")
    results = []
    for template_id in request.template_ids:
        item = templates[template_id]
        matches = [question for question in request.questions if re.search(item.pattern, question, re.I)]
        results.append({"template_id": template_id, "matches": len(matches), "total": len(request.questions), "hit_rate": round(len(matches) / len(request.questions), 4), "matched_questions": matches})
    return {"results": results, "winner": max(results, key=lambda result: result["hit_rate"])["template_id"]}

def audit(db, template_id, action, detail="", snapshot=None):
    db.add(LocalTemplateEvent(template_id=template_id, action=action, detail=detail, snapshot=json.dumps(snapshot, ensure_ascii=False) if snapshot else None))

def admin_audit(db, action, detail=""):
    db.add(TemplateAuditLog(action=action, detail=detail))

def snapshot_of(item):
    return {"template_id": item.template_id, "pattern": item.pattern, "answer": item.answer, "enabled": item.enabled}

def validate_answer_content(answer: str):
    if re.search(r"<\s*/?\s*script\b|javascript\s*:", answer, re.I):
        raise HTTPException(status_code=422, detail="模板答案包含不允许的脚本内容。")


@router.get("")
def list_templates(enabled: bool | None = Query(default=None), db: Session = Depends(get_db)):
    query = db.query(LocalTemplate).order_by(LocalTemplate.id.asc())
    if enabled is not None:
        query = query.filter(LocalTemplate.enabled == enabled)
    items = query.all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.get("/stats")
def template_stats(db: Session = Depends(get_db)):
    items = db.query(LocalTemplate).all()
    counts = {status: sum(1 for item in items if item.review_status == status) for status in ("pending", "approved", "rejected")}
    return {"total": len(items), "enabled": sum(1 for item in items if item.enabled), "by_status": counts}


@router.post("", status_code=201)
def create_template(request: TemplateRequest, db: Session = Depends(get_db)):
    validate_answer_content(request.answer)
    try: re.compile(request.pattern)
    except re.error as exc: raise HTTPException(status_code=422, detail=f"匹配正则无效：{exc}") from exc
    if db.query(LocalTemplate).filter(LocalTemplate.template_id == request.template_id).first():
        raise HTTPException(status_code=409, detail="模板 ID 已存在。")
    item = LocalTemplate(**request.model_dump(), review_status="pending")
    db.add(item); audit(db, request.template_id, "created"); admin_audit(db, "template_created", request.template_id); db.commit(); db.refresh(item)
    return serialize(item)


@router.post("/preview")
def preview_template(request: TemplatePreview, db: Session = Depends(get_db)):
    query = db.query(LocalTemplate).filter(LocalTemplate.enabled.is_(True))
    if request.template_id:
        query = query.filter(LocalTemplate.template_id == request.template_id)
    import re
    for item in query.order_by(LocalTemplate.id.asc()).all():
        try:
            if re.search(item.pattern, request.question, re.I):
                return {"matched": True, "template_id": item.template_id, "answer": item.answer}
        except re.error:
            continue
    return {"matched": False, "template_id": request.template_id, "answer": None}


@router.get("/export")
def export_templates(db: Session = Depends(get_db)):
    items = db.query(LocalTemplate).order_by(LocalTemplate.id.asc()).all()
    admin_audit(db, "export", f"count={len(items)}"); db.commit()
    return {"version": 1, "items": [serialize(item) for item in items]}


@router.post("/import")
def import_templates(request: TemplateImport, db: Session = Depends(get_db)):
    created = updated = 0
    for incoming in request.items:
        validate_answer_content(incoming.answer)
        try: re.compile(incoming.pattern)
        except re.error as exc: raise HTTPException(status_code=422, detail=f"模板 {incoming.template_id} 的正则无效：{exc}") from exc
        item = db.query(LocalTemplate).filter(LocalTemplate.template_id == incoming.template_id).first()
        if item is None:
            item = LocalTemplate(**incoming.model_dump(), review_status="pending"); db.add(item); audit(db, incoming.template_id, "imported"); created += 1
        else:
            before = snapshot_of(item)
            item.pattern, item.answer, item.enabled = incoming.pattern, incoming.answer, incoming.enabled
            audit(db, incoming.template_id, "imported_update", "import", before); updated += 1
    db.commit()
    return {"created": created, "updated": updated, "total": len(request.items)}


@router.put("/{template_id}")
def update_template(template_id: str, request: TemplateUpdate, db: Session = Depends(get_db)):
    item = db.query(LocalTemplate).filter(LocalTemplate.template_id == template_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="模板不存在。")
    if request.pattern is not None:
        try: re.compile(request.pattern)
        except re.error as exc: raise HTTPException(status_code=422, detail=f"匹配正则无效：{exc}") from exc
    if request.answer is not None:
        validate_answer_content(request.answer)
    before = snapshot_of(item)
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    audit(db, template_id, "updated", ",".join(request.model_dump(exclude_unset=True).keys()), before); admin_audit(db, "template_updated", template_id); db.commit(); db.refresh(item)
    return serialize(item)


@router.post("/{template_id}/review")
def review_template(template_id: str, status: str = Query(..., pattern="^(approved|rejected|pending)$"), db: Session = Depends(get_db)):
    item = db.query(LocalTemplate).filter(LocalTemplate.template_id == template_id).first()
    if item is None: raise HTTPException(status_code=404, detail="模板不存在。")
    item.review_status = status
    audit(db, template_id, "reviewed", status); admin_audit(db, "template_reviewed", f"{template_id}:{status}"); db.commit(); db.refresh(item)
    return serialize(item)


@router.delete("/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db)):
    item = db.query(LocalTemplate).filter(LocalTemplate.template_id == template_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="模板不存在。")
    db.delete(item); audit(db, template_id, "deleted", snapshot=snapshot_of(item)); admin_audit(db, "template_deleted", template_id); db.commit()
    return {"deleted": True, "template_id": template_id}


@router.get("/{template_id}/events")
def template_events(template_id: str, db: Session = Depends(get_db)):
    events = db.query(LocalTemplateEvent).filter(LocalTemplateEvent.template_id == template_id).order_by(LocalTemplateEvent.created_at.desc()).all()
    return {"template_id": template_id, "events": [{"id": event.id, "action": event.action, "detail": event.detail, "created_at": event.created_at.isoformat()} for event in events]}


@router.post("/{template_id}/rollback/{event_id}")
def rollback_template(template_id: str, event_id: int, db: Session = Depends(get_db)):
    event = db.query(LocalTemplateEvent).filter(LocalTemplateEvent.id == event_id, LocalTemplateEvent.template_id == template_id).first()
    if event is None or not event.snapshot:
        raise HTTPException(status_code=404, detail="没有可回滚的模板快照。")
    data = json.loads(event.snapshot)
    item = db.query(LocalTemplate).filter(LocalTemplate.template_id == template_id).first()
    if item is None:
        item = LocalTemplate(**data); db.add(item)
    else:
        before = snapshot_of(item)
        item.pattern, item.answer, item.enabled = data["pattern"], data["answer"], data["enabled"]
        audit(db, template_id, "rollback", f"from_event={event_id}", before); admin_audit(db, "template_rollback", f"{template_id}:{event_id}")
    db.commit(); db.refresh(item)
    return serialize(item)
