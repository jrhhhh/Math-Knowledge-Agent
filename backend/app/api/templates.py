import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.ai import get_db
from app.models.local_template import LocalTemplate
from app.models.local_template_event import LocalTemplateEvent

router = APIRouter(prefix="/local-templates", tags=["Local answer templates"])


class TemplateRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=100)
    pattern: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1)
    enabled: bool = True


class TemplateUpdate(BaseModel):
    pattern: str | None = Field(default=None, min_length=1, max_length=500)
    answer: str | None = Field(default=None, min_length=1)
    enabled: bool | None = None


class TemplatePreview(BaseModel):
    question: str = Field(min_length=1)
    template_id: str | None = None

class TemplateImport(BaseModel):
    items: list[TemplateRequest] = Field(min_length=1, max_length=500)


def serialize(item):
    return {"id": item.id, "template_id": item.template_id, "pattern": item.pattern, "answer": item.answer, "enabled": item.enabled, "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat()}

def audit(db, template_id, action, detail="", snapshot=None):
    db.add(LocalTemplateEvent(template_id=template_id, action=action, detail=detail, snapshot=json.dumps(snapshot, ensure_ascii=False) if snapshot else None))

def snapshot_of(item):
    return {"template_id": item.template_id, "pattern": item.pattern, "answer": item.answer, "enabled": item.enabled}


@router.get("")
def list_templates(enabled: bool | None = Query(default=None), db: Session = Depends(get_db)):
    query = db.query(LocalTemplate).order_by(LocalTemplate.id.asc())
    if enabled is not None:
        query = query.filter(LocalTemplate.enabled == enabled)
    items = query.all()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("", status_code=201)
def create_template(request: TemplateRequest, db: Session = Depends(get_db)):
    if db.query(LocalTemplate).filter(LocalTemplate.template_id == request.template_id).first():
        raise HTTPException(status_code=409, detail="模板 ID 已存在。")
    item = LocalTemplate(**request.model_dump())
    db.add(item); audit(db, request.template_id, "created"); db.commit(); db.refresh(item)
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
    return {"version": 1, "items": [serialize(item) for item in items]}


@router.post("/import")
def import_templates(request: TemplateImport, db: Session = Depends(get_db)):
    created = updated = 0
    for incoming in request.items:
        item = db.query(LocalTemplate).filter(LocalTemplate.template_id == incoming.template_id).first()
        if item is None:
            item = LocalTemplate(**incoming.model_dump()); db.add(item); audit(db, incoming.template_id, "imported"); created += 1
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
    before = snapshot_of(item)
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    audit(db, template_id, "updated", ",".join(request.model_dump(exclude_unset=True).keys()), before); db.commit(); db.refresh(item)
    return serialize(item)


@router.delete("/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db)):
    item = db.query(LocalTemplate).filter(LocalTemplate.template_id == template_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="模板不存在。")
    db.delete(item); audit(db, template_id, "deleted", snapshot=snapshot_of(item)); db.commit()
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
        audit(db, template_id, "rollback", f"from_event={event_id}", before)
    db.commit(); db.refresh(item)
    return serialize(item)
