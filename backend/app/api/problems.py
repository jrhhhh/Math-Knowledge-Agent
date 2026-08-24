from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.problem import Problem


router = APIRouter(
    prefix="/problems",
    tags=["Problems"]
)


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()



@router.post("/")
def create_problem(
    problem: dict,
    db: Session = Depends(get_db)
):

    new_problem = Problem(
        title=problem["title"],
        content=problem["content"],
        solution=problem.get("solution"),
        difficulty=problem.get("difficulty")
    )

    db.add(new_problem)
    db.commit()
    db.refresh(new_problem)

    return new_problem



@router.get("/")
def get_problems(
    db: Session = Depends(get_db)
):

    return db.query(Problem).all()