from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.concept import Concept


router = APIRouter(
    prefix="/concepts",
    tags=["Concepts"]
)


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()



@router.post("/")
def create_concept(
    name: str,
    description: str,
    field: str,
    db: Session = Depends(get_db)
):

    concept = Concept(
        name=name,
        description=description,
        field=field
    )

    db.add(concept)

    db.commit()

    db.refresh(concept)

    return concept



@router.get("/")
def get_concepts(
    db: Session = Depends(get_db)
):

    return db.query(Concept).all()
@router.delete("/{concept_id}")
def delete_concept(
    concept_id: int,
    db: Session = Depends(get_db)
):

    concept = db.query(Concept).filter(
        Concept.id == concept_id
    ).first()


    if concept is None:
        return {
            "message": "Concept not found"
        }


    db.delete(concept)

    db.commit()


    return {
        "message": "Deleted successfully"
    }
@router.get("/{concept_id}")
def get_concept(
    concept_id: int,
    db: Session = Depends(get_db)
):

    concept = db.query(Concept).filter(
        Concept.id == concept_id
    ).first()


    if concept is None:
        return {
            "message": "Concept not found"
        }


    return concept