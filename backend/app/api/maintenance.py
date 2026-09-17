from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.ai import get_db

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])

@router.get("/integrity")
def integrity_report(db: Session = Depends(get_db)):
    checks = {
        "orphan_problem_concepts": db.execute(text("SELECT COUNT(*) FROM problem_concepts pc LEFT JOIN problems p ON p.id=pc.problem_id WHERE p.id IS NULL OR pc.concept_id NOT IN (SELECT id FROM concepts)" )).scalar_one(),
        "orphan_relations": db.execute(text("SELECT COUNT(*) FROM concept_relations r LEFT JOIN concepts s ON s.id=r.source_concept_id LEFT JOIN concepts t ON t.id=r.target_concept_id WHERE s.id IS NULL OR t.id IS NULL" )).scalar_one(),
        "duplicate_relations": db.execute(text("SELECT COUNT(*) FROM (SELECT source_concept_id,target_concept_id,relation,COUNT(*) c FROM concept_relations GROUP BY source_concept_id,target_concept_id,relation HAVING c > 1)" )).scalar_one(),
        "duplicate_concept_names": db.execute(text("SELECT COUNT(*) FROM (SELECT name,COUNT(*) c FROM concepts GROUP BY name HAVING c > 1)" )).scalar_one(),
    }
    return {"healthy": not any(checks.values()), "checks": checks}
