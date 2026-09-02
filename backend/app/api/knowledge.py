from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.concept import Concept
from app.models.concept_relation import ConceptRelation
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept


router = APIRouter(
    prefix="/knowledge",
    tags=["Knowledge"]
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.get("/{concept_id}")
def get_knowledge(
    concept_id: int,
    db: Session = Depends(get_db)
):
    """
    获取一个知识点的完整知识信息。
    """

    # 1. 查找知识点
    concept = db.query(Concept).filter(
        Concept.id == concept_id
    ).first()

    if concept is None:
        raise HTTPException(
            status_code=404,
            detail="Concept not found"
        )

    # 2. 前置知识
    prerequisite_relations = db.query(
        ConceptRelation
    ).filter(
        ConceptRelation.target_concept_id == concept.id,
        ConceptRelation.relation == "prerequisite"
    ).all()

    prerequisites = []

    for relation in prerequisite_relations:

        prerequisite = db.query(Concept).filter(
            Concept.id == relation.source_concept_id
        ).first()

        if prerequisite is not None:
            prerequisites.append({
                "id": prerequisite.id,
                "name": prerequisite.name,
                "type": prerequisite.type,
                "weight": relation.weight
            })

    # 3. 支持当前知识点的知识
    support_relations = db.query(
        ConceptRelation
    ).filter(
        ConceptRelation.target_concept_id == concept.id,
        ConceptRelation.relation == "supports"
    ).all()

    supports = []

    for relation in support_relations:

        source = db.query(Concept).filter(
            Concept.id == relation.source_concept_id
        ).first()

        if source is not None:
            supports.append({
                "id": source.id,
                "name": source.name,
                "type": source.type,
                "weight": relation.weight
            })

    # 4. 与当前知识点相关的其他知识
    related_relations = db.query(
        ConceptRelation
    ).filter(
        (
            (ConceptRelation.source_concept_id == concept.id)
            |
            (ConceptRelation.target_concept_id == concept.id)
        ),
        ConceptRelation.relation == "related"
    ).all()

    related = []

    for relation in related_relations:

        if relation.source_concept_id == concept.id:
            other_id = relation.target_concept_id
        else:
            other_id = relation.source_concept_id

        other = db.query(Concept).filter(
            Concept.id == other_id
        ).first()

        if other is not None:
            related.append({
                "id": other.id,
                "name": other.name,
                "type": other.type,
                "weight": relation.weight
            })

    # 5. 相关题目
    problem_relations = db.query(
        ProblemConcept
    ).filter(
        ProblemConcept.concept_id == concept.id
    ).all()

    problems = []

    for relation in problem_relations:

        problem = db.query(Problem).filter(
            Problem.id == relation.problem_id
        ).first()

        if problem is not None:
            problems.append({
                "id": problem.id,
                "title": problem.title,
                "difficulty": problem.difficulty,
                "importance": relation.importance
            })

    # 6. 返回知识信息
    return {
        "concept": {
            "id": concept.id,
            "name": concept.name,
            "type": concept.type,
            "description": concept.description,
            "field": concept.field,
            "level": concept.level
        },

        "prerequisites": prerequisites,

        "supports": supports,

        "related": related,

        "problems": problems
    }