import os
import sqlite3
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.ai import get_db
from app.security import require_admin
from app.database import engine

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])

class RepairRequest(BaseModel):
    orphan_problem_concept_ids: list[int] = Field(default_factory=list, max_length=200)
    orphan_relation_ids: list[int] = Field(default_factory=list, max_length=200)
    duplicate_relation_ids: list[int] = Field(default_factory=list, max_length=200)

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
def repair_integrity(request: RepairRequest, db: Session = Depends(get_db), _: bool = Depends(require_admin)):
    ids = {key: sorted(set(values)) for key, values in request.model_dump().items()}
    total = sum(len(values) for values in ids.values())
    if total == 0:
        raise HTTPException(status_code=422, detail="至少指定一条待修复记录。")
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
    return {"deleted": deleted, "backup_path": backup_path, "message": "修复完成，已先生成备份。"}
