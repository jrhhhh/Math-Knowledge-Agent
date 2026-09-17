import os
import sqlite3
import secrets
import time
import json
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.ai import get_db
from app.security import require_admin, record_security_event
from app.database import engine

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])

class RepairRequest(BaseModel):
    confirmation_token: str | None = None
    orphan_problem_concept_ids: list[int] = Field(default_factory=list, max_length=200)
    orphan_relation_ids: list[int] = Field(default_factory=list, max_length=200)
    duplicate_relation_ids: list[int] = Field(default_factory=list, max_length=200)

_repair_tokens = {}

def _repair_key(request):
    data = request.model_dump(exclude={"confirmation_token"})
    return repr({key: sorted(set(value)) for key, value in data.items()})

@router.get("/integrity")
def integrity_report(db: Session = Depends(get_db)):
    checks = {
        "orphan_problem_concepts": db.execute(text("SELECT COUNT(*) FROM problem_concepts pc LEFT JOIN problems p ON p.id=pc.problem_id WHERE p.id IS NULL OR pc.concept_id NOT IN (SELECT id FROM concepts)" )).scalar_one(),
        "orphan_relations": db.execute(text("SELECT COUNT(*) FROM concept_relations r LEFT JOIN concepts s ON s.id=r.source_concept_id LEFT JOIN concepts t ON t.id=r.target_concept_id WHERE s.id IS NULL OR t.id IS NULL" )).scalar_one(),
        "duplicate_relations": db.execute(text("SELECT COUNT(*) FROM (SELECT source_concept_id,target_concept_id,relation,COUNT(*) c FROM concept_relations GROUP BY source_concept_id,target_concept_id,relation HAVING c > 1)" )).scalar_one(),
        "duplicate_concept_names": db.execute(text("SELECT COUNT(*) FROM (SELECT name,COUNT(*) c FROM concepts GROUP BY name HAVING c > 1)" )).scalar_one(),
    }
    return {"healthy": not any(checks.values()), "checks": checks}

@router.get("/integrity/repair-preview")
def repair_preview(limit: int = 100, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 500))
    orphan_links = db.execute(text("SELECT pc.id, pc.problem_id, pc.concept_id FROM problem_concepts pc LEFT JOIN problems p ON p.id=pc.problem_id LEFT JOIN concepts c ON c.id=pc.concept_id WHERE p.id IS NULL OR c.id IS NULL LIMIT :limit"), {"limit": limit}).mappings().all()
    orphan_relations = db.execute(text("SELECT r.id, r.source_concept_id, r.target_concept_id, r.relation FROM concept_relations r LEFT JOIN concepts s ON s.id=r.source_concept_id LEFT JOIN concepts t ON t.id=r.target_concept_id WHERE s.id IS NULL OR t.id IS NULL LIMIT :limit"), {"limit": limit}).mappings().all()
    duplicates = db.execute(text("SELECT MIN(id) AS keep_id, source_concept_id, target_concept_id, relation, COUNT(*) AS duplicate_count FROM concept_relations GROUP BY source_concept_id,target_concept_id,relation HAVING COUNT(*) > 1 LIMIT :limit"), {"limit": limit}).mappings().all()
    return {"read_only": True, "items": {"orphan_problem_concepts": [dict(row) for row in orphan_links],
            "orphan_relations": [dict(row) for row in orphan_relations], "duplicate_relations": [dict(row) for row in duplicates]},
            "recommendation": "请人工确认后再执行修复；本接口不会修改数据。"}

@router.post("/integrity/repair")
def repair_integrity(request: RepairRequest, http_request: Request, db: Session = Depends(get_db), _: bool = Depends(require_admin)):
    ids = {key: sorted(set(values)) for key, values in request.model_dump(exclude={"confirmation_token"}).items()}
    total = sum(len(values) for values in ids.values())
    if total == 0:
        raise HTTPException(status_code=422, detail="至少指定一条待修复记录。")
    token_data = _repair_tokens.pop(request.confirmation_token or "", None)
    if not token_data or token_data["expires_at"] <= time.time() or token_data["key"] != _repair_key(request):
        raise HTTPException(status_code=409, detail="确认令牌无效、已过期或与修复内容不匹配。")
    backup_dir = os.getenv("MATH_AGENT_BACKUP_DIR", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, f"math_agent-before-repair-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db")
    source = engine.raw_connection()
    destination = sqlite3.connect(backup_path)
    try:
        source.driver_connection.backup(destination)
        destination.commit()
    finally:
        destination.close(); source.close()
    deleted = {"orphan_problem_concepts": 0, "orphan_relations": 0, "duplicate_relations": 0}
    for key, table in (("orphan_problem_concept_ids", "problem_concepts"), ("orphan_relation_ids", "concept_relations"), ("duplicate_relation_ids", "concept_relations")):
        if ids[key]:
            result = db.execute(text(f"DELETE FROM {table} WHERE id IN ({','.join(str(i) for i in ids[key])})"))
            deleted[key.replace("_ids", "")] = result.rowcount
    db.commit()
    record_security_event("integrity_repaired", http_request, json.dumps({"deleted": deleted, "backup_path": backup_path, "ids": ids}, ensure_ascii=False))
    return {"deleted": deleted, "backup_path": backup_path, "message": "修复完成，已先生成备份。"}

@router.post("/backup")
def create_backup(_: bool = Depends(require_admin)):
    backup_dir = os.getenv("MATH_AGENT_BACKUP_DIR", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    path = os.path.join(backup_dir, f"math_agent-manual-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db")
    source = engine.raw_connection()
    destination = sqlite3.connect(path)
    try:
        source.driver_connection.backup(destination)
        destination.commit()
    finally:
        destination.close(); source.close()
    return {"created": True, "path": path, "size_bytes": os.path.getsize(path)}

@router.get("/backups")
def list_backups(limit: int = 20):
    backup_dir = Path(os.getenv("MATH_AGENT_BACKUP_DIR", "backups"))
    if not backup_dir.exists():
        return {"items": [], "total": 0}
    files = sorted(backup_dir.glob("math_agent-*.db"), key=lambda item: item.stat().st_mtime, reverse=True)[:max(1, min(limit, 100))]
    return {"items": [{"path": str(item), "size_bytes": item.stat().st_size, "modified_at": datetime.fromtimestamp(item.stat().st_mtime).isoformat()} for item in files], "total": len(files)}

@router.post("/integrity/repair/prepare")
def prepare_integrity_repair(request: RepairRequest, _: bool = Depends(require_admin)):
    if sum(len(values) for key, values in request.model_dump(exclude={"confirmation_token"}).items()) == 0:
        raise HTTPException(status_code=422, detail="至少指定一条待修复记录。")
    token = secrets.token_urlsafe(24)
    _repair_tokens[token] = {"key": _repair_key(request), "expires_at": time.time() + 600}
    return {"confirmation_token": token, "expires_in": 600, "message": "请核对修复内容后，将令牌用于执行接口。"}
