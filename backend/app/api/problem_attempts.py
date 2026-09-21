from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.problem import Problem
from app.models.problem_attempt import ProblemAttempt


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
    db.commit()
    db.refresh(attempt)
    return attempt_response(attempt)
