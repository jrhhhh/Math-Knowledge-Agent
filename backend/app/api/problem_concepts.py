from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.problem_concept import ProblemConcept


router = APIRouter(
    prefix="/problem-concepts",
    tags=["problem-concepts"]
)


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()



@router.post("/")
def create_problem_concept(
    data: dict,
    db: Session = Depends(get_db)
):

    relation = ProblemConcept(
        problem_id=data["problem_id"],
        concept_id=data["concept_id"],
        relation=data.get(
            "relation",
            "related"
        ),
        importance=data.get(
            "importance",
            1.0
        )
    )


    db.add(relation)
    db.commit()
    db.refresh(relation)


    return relation



@router.get("/")
def get_problem_concepts(
    db: Session = Depends(get_db)
):

    return db.query(
        ProblemConcept
    ).all()