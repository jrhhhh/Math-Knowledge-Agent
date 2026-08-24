from fastapi import APIRouter, Depends, HTTPException
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

@router.delete("/{problem_id}")
def delete_problem(
    problem_id: int,
    db: Session = Depends(get_db)
):

    problem = db.query(Problem).filter(
        Problem.id == problem_id
    ).first()


    if problem is None:
        raise HTTPException(
            status_code=404,
            detail="Problem not found"
        )


    db.delete(problem)
    db.commit()


    return {
        "message": "Problem deleted successfully"
    }
@router.put("/{problem_id}")
def update_problem(
    problem_id: int,
    problem: dict,
    db: Session = Depends(get_db)
):

    existing_problem = db.query(Problem).filter(
        Problem.id == problem_id
    ).first()


    if existing_problem is None:
        raise HTTPException(
            status_code=404,
            detail="Problem not found"
        )


    existing_problem.title = problem.get(
        "title",
        existing_problem.title
    )

    existing_problem.content = problem.get(
        "content",
        existing_problem.content
    )

    existing_problem.solution = problem.get(
        "solution",
        existing_problem.solution
    )

    existing_problem.difficulty = problem.get(
        "difficulty",
        existing_problem.difficulty
    )


    db.commit()
    db.refresh(existing_problem)


    return existing_problem