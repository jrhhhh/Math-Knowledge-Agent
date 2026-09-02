from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.concept import Concept
from app.models.concept_relation import ConceptRelation

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

@router.get("/graph")
def get_concept_graph(
    db: Session = Depends(get_db)
):
    concepts = db.query(Concept).all()

    relations = db.query(ConceptRelation).all()

    nodes = []

    for concept in concepts:
        nodes.append({
            "id": concept.id,
            "name": concept.name,
            "type": concept.type,
            "description": concept.description,
            "field": concept.field,
            "level": concept.level
        })

    edges = []

    for relation in relations:
        edges.append({
            "source": relation.source_concept_id,
            "target": relation.target_concept_id,
            "relation": relation.relation,
            "weight": relation.weight
        })

    return {
        "nodes": nodes,
        "edges": edges
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

@router.get("/{concept_id}/relations")
def get_concept_relations(
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

    relations = db.query(ConceptRelation).filter(
        (ConceptRelation.source_concept_id == concept_id)
        |
        (ConceptRelation.target_concept_id == concept_id)
    ).all()

    prerequisites = []
    next_concepts = []
    related = []

    for relation in relations:

        if relation.source_concept_id == concept_id:

            target = db.query(Concept).filter(
                Concept.id == relation.target_concept_id
            ).first()

            if target is None:
                continue

            item = {
                "id": target.id,
                "name": target.name,
                "type": target.type,
                "relation": relation.relation,
                "weight": relation.weight
            }

            if relation.relation == "prerequisite":
                next_concepts.append(item)

            else:
                related.append(item)

        else:

            source = db.query(Concept).filter(
                Concept.id == relation.source_concept_id
            ).first()

            if source is None:
                continue

            item = {
                "id": source.id,
                "name": source.name,
                "type": source.type,
                "relation": relation.relation,
                "weight": relation.weight
            }

            if relation.relation == "prerequisite":
                prerequisites.append(item)

            else:
                related.append(item)

    return {
        "concept": {
            "id": concept.id,
            "name": concept.name,
            "type": concept.type
        },
        "prerequisites": prerequisites,
        "next_concepts": next_concepts,
        "related": related
    }

@router.get("/{concept_id}/prerequisites")
def get_prerequisites(
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

    visited = set()
    result = []

    def traverse(current_id: int, depth: int):
        relations = db.query(ConceptRelation).filter(
            ConceptRelation.target_concept_id == current_id,
            ConceptRelation.relation == "prerequisite"
        ).all()

        for relation in relations:

            prerequisite_id = relation.source_concept_id

            if prerequisite_id in visited:
                continue

            visited.add(prerequisite_id)

            prerequisite = db.query(Concept).filter(
                Concept.id == prerequisite_id
            ).first()

            if prerequisite is None:
                continue

            result.append({
                "id": prerequisite.id,
                "name": prerequisite.name,
                "type": prerequisite.type,
                "depth": depth,
                "weight": relation.weight
            })

            traverse(
                prerequisite.id,
                depth + 1
            )

    traverse(
        concept_id,
        1
    )

    return {
        "concept": {
            "id": concept.id,
            "name": concept.name,
            "type": concept.type
        },
        "prerequisites": result
    }