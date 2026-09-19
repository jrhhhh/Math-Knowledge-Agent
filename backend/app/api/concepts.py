from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.concept import Concept
from app.models.concept_relation import ConceptRelation
from app.models.concept_alias import ConceptAlias
from app.models.concept_learning_progress import ConceptLearningProgress

router = APIRouter(
    prefix="/concepts",
    tags=["Concepts"]
)


class AliasRequest(BaseModel):
    alias: str


class LearningProgressRequest(BaseModel):
    status: str = Field(pattern="^(learning|completed)$")
    profile_id: str = Field(default="local", min_length=1, max_length=80)


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


@router.get("/search")
def search_concepts(q: str = Query(default="", max_length=120), limit: int = Query(default=12, ge=1, le=50), db: Session = Depends(get_db)):
    """Search persisted concepts without asking the model to regenerate a graph."""
    query = db.query(Concept)
    term = q.strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(
            (Concept.name.ilike(pattern))
            | (Concept.description.ilike(pattern))
            | (Concept.field.ilike(pattern))
        )
    concepts = query.order_by(Concept.level.asc(), Concept.name.asc()).limit(limit).all()
    return {
        "query": term,
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "type": item.type,
                "field": item.field,
                "description": item.description,
            }
            for item in concepts
        ],
        "total": len(concepts),
    }


@router.get("/{concept_id}/network")
def get_concept_network(concept_id: int, db: Session = Depends(get_db)):
    """Return one persisted concept and its directly connected network."""
    concept = db.query(Concept).filter(Concept.id == concept_id).first()
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    relations = db.query(ConceptRelation).filter(
        (ConceptRelation.source_concept_id == concept_id)
        | (ConceptRelation.target_concept_id == concept_id)
    ).all()
    node_ids = {concept_id}
    for relation in relations:
        node_ids.update((relation.source_concept_id, relation.target_concept_id))
    nodes = db.query(Concept).filter(Concept.id.in_(node_ids)).order_by(Concept.level.asc(), Concept.id.asc()).all()
    return {
        "focus_id": concept_id,
        "nodes": [{"id": item.id, "name": item.name, "type": item.type, "field": item.field, "description": item.description} for item in nodes],
        "edges": [{"source": item.source_concept_id, "target": item.target_concept_id, "relation": item.relation, "weight": item.weight} for item in relations],
    }


@router.get("/learning-progress")
def get_learning_progress(profile_id: str = "local", db: Session = Depends(get_db)):
    items = db.query(ConceptLearningProgress).filter(ConceptLearningProgress.profile_id == profile_id).order_by(ConceptLearningProgress.updated_at.desc()).all()
    completed_ids = [item.concept_id for item in items if item.status == "completed"]
    total_concepts = db.query(Concept).count()
    next_concepts = db.query(Concept).filter(~Concept.id.in_(completed_ids)).order_by(Concept.level.asc(), Concept.id.asc()).limit(3).all()
    return {
        "profile_id": profile_id,
        "items": [
            {
                "concept_id": item.concept_id,
                "status": item.status,
                "updated_at": item.updated_at.isoformat(),
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            }
            for item in items
        ],
        "completed_concept_ids": completed_ids,
        "summary": {
            "completed": len(completed_ids),
            "total": total_concepts,
            "percent": round((len(completed_ids) / total_concepts * 100) if total_concepts else 0),
            "next_concepts": [{"id": item.id, "name": item.name, "type": item.type} for item in next_concepts],
        },
    }


@router.put("/{concept_id}/learning-progress")
def set_learning_progress(concept_id: int, request: LearningProgressRequest, db: Session = Depends(get_db)):
    if db.query(Concept).filter(Concept.id == concept_id).first() is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    item = db.query(ConceptLearningProgress).filter(
        ConceptLearningProgress.profile_id == request.profile_id,
        ConceptLearningProgress.concept_id == concept_id,
    ).first()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if item is None:
        item = ConceptLearningProgress(profile_id=request.profile_id, concept_id=concept_id, status=request.status)
        db.add(item)
    else:
        item.status = request.status
    item.completed_at = now if request.status == "completed" else None
    item.updated_at = now
    db.commit()
    db.refresh(item)
    return {
        "concept_id": item.concept_id,
        "profile_id": item.profile_id,
        "status": item.status,
        "updated_at": item.updated_at.isoformat(),
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
    }


@router.post("/{concept_id}/aliases")
def add_concept_alias(concept_id: int, request: AliasRequest, db: Session = Depends(get_db)):
    concept = db.query(Concept).filter(Concept.id == concept_id).first()
    alias = request.alias.strip()
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    if not alias:
        raise HTTPException(status_code=400, detail="alias 不能为空。")
    existing = db.query(ConceptAlias).filter(ConceptAlias.alias == alias).first()
    if existing is not None:
        if existing.concept_id == concept_id:
            return {"id": existing.id, "concept_id": concept_id, "alias": existing.alias}
        raise HTTPException(status_code=409, detail="该别名已绑定到其他知识点。")
    item = ConceptAlias(concept_id=concept_id, alias=alias)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "concept_id": item.concept_id, "alias": item.alias}


@router.get("/{concept_id}/aliases")
def get_concept_aliases(concept_id: int, db: Session = Depends(get_db)):
    concept = db.query(Concept).filter(Concept.id == concept_id).first()
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    return {
        "concept": {"id": concept.id, "name": concept.name},
        "aliases": [
            {"id": item.id, "alias": item.alias}
            for item in db.query(ConceptAlias).filter(ConceptAlias.concept_id == concept_id).all()
        ],
    }
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


@router.get("/{concept_id}/learning-path")
def get_learning_path(concept_id: int, max_depth: int = 4, db: Session = Depends(get_db)):
    """Return a deterministic prerequisite-first path for one concept.

    The graph can contain imperfect imported relations, so cycles are detected
    and reported instead of recursing forever. The target itself is always the
    final step, which makes the result directly usable by the learning UI.
    """
    max_depth = min(max(1, max_depth), 8)
    concept = db.query(Concept).filter(Concept.id == concept_id).first()
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    concepts = {item.id: item for item in db.query(Concept).all()}
    parent_relations = {}
    for relation in db.query(ConceptRelation).filter(ConceptRelation.relation == "prerequisite").all():
        parent_relations.setdefault(relation.target_concept_id, []).append(relation)
    for relations in parent_relations.values():
        relations.sort(key=lambda item: (-float(item.weight or 0), item.source_concept_id))

    visited, visiting, steps = set(), set(), []
    cycle_detected = False

    def visit(current_id: int, depth: int):
        nonlocal cycle_detected
        if current_id in visiting:
            cycle_detected = True
            return
        if current_id in visited or depth > max_depth:
            return
        visiting.add(current_id)
        for relation in parent_relations.get(current_id, []):
            visit(relation.source_concept_id, depth + 1)
        visiting.remove(current_id)
        visited.add(current_id)
        current = concepts.get(current_id)
        if current is not None and current_id != concept_id:
            steps.append({
                "id": current.id,
                "name": current.name,
                "type": current.type,
                "depth": depth,
                "stage": "foundation" if depth > 1 else "bridge",
            })

    visit(concept_id, 0)
    steps.append({
        "id": concept.id,
        "name": concept.name,
        "type": concept.type,
        "depth": 0,
        "stage": "focus",
    })
    return {
        "concept": {"id": concept.id, "name": concept.name, "type": concept.type},
        "steps": steps,
        "cycle_detected": cycle_detected,
        "max_depth": max_depth,
    }
