from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.problem import Problem
from app.models.problem_attempt import ProblemAttempt
from app.models.problem_hint import ProblemHint
from app.models.problem_concept import ProblemConcept
from app.models.concept import Concept
from app.models.concept_learning_progress import ConceptLearningProgress
from app.models.concept_relation import ConceptRelation


router = APIRouter(prefix="/problems", tags=["Problem Attempts"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def attempt_response(attempt: ProblemAttempt) -> dict:
    return {
        "id": attempt.id,
        "problem_id": attempt.problem_id,
        "answer": attempt.answer,
        "status": attempt.status,
        "correctness": attempt.correctness,
        "error_type": attempt.error_type,
        "feedback": attempt.feedback,
        "hint_level": attempt.hint_level,
        "independent": attempt.independent,
        "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
        "reviewed_at": attempt.reviewed_at.isoformat() if attempt.reviewed_at else None,
    }


@router.post("/{problem_id}/attempts")
def submit_attempt(problem_id: int, payload: dict, db: Session = Depends(get_db)):
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    answer = str(payload.get("answer", "")).strip()
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found")
    if not answer:
        raise HTTPException(status_code=422, detail="answer 不能为空")
    attempt = ProblemAttempt(
        problem_id=problem_id,
        answer=answer,
        hint_level=max(0, int(payload.get("hint_level", 0) or 0)),
        independent="yes" if payload.get("independent") is True else "unknown",
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return {**attempt_response(attempt), "message": "作答已记录，数学正确性等待审核。"}


@router.get("/{problem_id}/hints")
def list_hints(problem_id: int, level: int = 0, db: Session = Depends(get_db)):
    if db.query(Problem).filter(Problem.id == problem_id).first() is None:
        raise HTTPException(status_code=404, detail="Problem not found")
    level = max(0, min(int(level), 5))
    query = db.query(ProblemHint).filter(ProblemHint.problem_id == problem_id, ProblemHint.review_status == "approved")
    if level:
        query = query.filter(ProblemHint.level <= level)
    hints = query.order_by(ProblemHint.level.asc()).all()
    return {"problem_id": problem_id, "level": level, "items": [{"level": item.level, "content": item.content} for item in hints], "max_level": db.query(ProblemHint).filter(ProblemHint.problem_id == problem_id, ProblemHint.review_status == "approved").count()}


@router.get("/{problem_id}/attempts")
def list_attempts(problem_id: int, db: Session = Depends(get_db)):
    if db.query(Problem).filter(Problem.id == problem_id).first() is None:
        raise HTTPException(status_code=404, detail="Problem not found")
    attempts = db.query(ProblemAttempt).filter(ProblemAttempt.problem_id == problem_id).order_by(ProblemAttempt.id.desc()).all()
    return {"problem_id": problem_id, "items": [attempt_response(item) for item in attempts]}


@router.put("/attempts/{attempt_id}/review")
def review_attempt(attempt_id: int, payload: dict, db: Session = Depends(get_db)):
    attempt = db.query(ProblemAttempt).filter(ProblemAttempt.id == attempt_id).first()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    correctness = payload.get("correctness")
    if correctness not in {"correct", "partially_correct", "incorrect", "unverified"}:
        raise HTTPException(status_code=422, detail="correctness 必须是可审核状态")
    attempt.correctness = correctness
    attempt.status = "reviewed" if correctness != "unverified" else "submitted"
    attempt.error_type = str(payload["error_type"]).strip() if payload.get("error_type") else None
    attempt.feedback = str(payload["feedback"]).strip() if payload.get("feedback") else None
    attempt.independent = "yes" if payload.get("independent") is True else ("no" if payload.get("independent") is False else attempt.independent)
    attempt.reviewed_at = datetime.utcnow() if attempt.status == "reviewed" else None
    learning_update = update_learning_from_attempt(attempt, db)
    db.commit()
    db.refresh(attempt)
    return {**attempt_response(attempt), "learning_update": learning_update}


@router.get("/next")
def recommend_next_problem(problem_id: int | None = None, db: Session = Depends(get_db)):
    """Recommend a traceable remediation or retest problem from reviewed evidence."""
    current = db.query(Problem).filter(Problem.id == problem_id).first() if problem_id else None
    target_concept_ids = []
    reason = "继续练习当前知识点"
    if current:
        target_concept_ids = [link.concept_id for link in db.query(ProblemConcept).filter(ProblemConcept.problem_id == current.id).all()]
        latest = db.query(ProblemAttempt).filter(ProblemAttempt.problem_id == current.id).order_by(ProblemAttempt.id.desc()).first()
        if latest and latest.correctness in {"incorrect", "partially_correct"}:
            reason = "上一题尚未独立掌握，建议用同知识点重测"
    query = db.query(Problem)
    if target_concept_ids:
        query = query.join(ProblemConcept, ProblemConcept.problem_id == Problem.id).filter(ProblemConcept.concept_id.in_(target_concept_ids))
    if current:
        query = query.filter(Problem.id != current.id)
    candidates = query.order_by(Problem.id.asc()).all()
    if not candidates and current:
        candidates = [current]
        reason = "当前知识点暂无其他题目，建议重新作答"
    if not candidates:
        return {"item": None, "reason": "题库暂无可推荐练习"}
    def has_independent_success(item):
        return db.query(ProblemAttempt).filter(ProblemAttempt.problem_id == item.id, ProblemAttempt.correctness == "correct", ProblemAttempt.independent == "yes").first() is not None
    candidates.sort(key=lambda item: (has_independent_success(item), item.id))
    item = candidates[0]
    return {"reason": reason, "item": {"id": item.id, "title": item.title, "content": item.content, "difficulty": item.difficulty}}


def update_learning_from_attempt(attempt: ProblemAttempt, db: Session) -> dict:
    """Turn reviewed work into conservative learning evidence.

    Only an independently correct attempt can complete a concept. A prompted or
    partially correct attempt remains learning; an incorrect attempt exposes
    prerequisite concepts as remediation suggestions.
    """
    links = db.query(ProblemConcept).filter(ProblemConcept.problem_id == attempt.problem_id).all()
    if not links or attempt.correctness == "unverified":
        return {"updated_concept_ids": [], "remediation": []}
    now = datetime.utcnow()
    completed_ids = []
    for link in links:
        item = db.query(ConceptLearningProgress).filter(
            ConceptLearningProgress.profile_id == "local",
            ConceptLearningProgress.concept_id == link.concept_id,
        ).first()
        status = "completed" if attempt.correctness == "correct" and attempt.independent == "yes" else "learning"
        if item is None:
            item = ConceptLearningProgress(profile_id="local", concept_id=link.concept_id, status=status)
            db.add(item)
        else:
            # Never downgrade an independently mastered concept because of a later miss.
            if item.status != "completed":
                item.status = status
        item.updated_at = now
        if item.status == "completed":
            item.completed_at = item.completed_at or now
            completed_ids.append(link.concept_id)
        elif status == "learning":
            item.completed_at = None
    remediation = []
    if attempt.correctness in {"incorrect", "partially_correct"}:
        prerequisite_ids = set()
        for link in links:
            prerequisite_ids.update(
                relation.source_concept_id
                for relation in db.query(ConceptRelation).filter(ConceptRelation.target_concept_id == link.concept_id).all()
            )
        if prerequisite_ids:
            concepts = db.query(Concept).filter(Concept.id.in_(prerequisite_ids)).order_by(Concept.level.asc(), Concept.id.asc()).all()
            remediation = [{"id": item.id, "name": item.name, "type": item.type} for item in concepts[:5]]
    return {"updated_concept_ids": completed_ids, "remediation": remediation}
