from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.ai import get_db
from app.models.local_template import LocalTemplate

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


def serialize(item):
    return {"id": item.id, "template_id": item.template_id, "pattern": item.pattern, "answer": item.answer, "enabled": item.enabled, "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat()}


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
    db.add(item); db.commit(); db.refresh(item)
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


@router.put("/{template_id}")
def update_template(template_id: str, request: TemplateUpdate, db: Session = Depends(get_db)):
    item = db.query(LocalTemplate).filter(LocalTemplate.template_id == template_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="模板不存在。")
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit(); db.refresh(item)
    return serialize(item)


@router.delete("/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db)):
    item = db.query(LocalTemplate).filter(LocalTemplate.template_id == template_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="模板不存在。")
    db.delete(item); db.commit()
    return {"deleted": True, "template_id": template_id}
