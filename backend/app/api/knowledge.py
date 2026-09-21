from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.concept import Concept
from app.models.concept_relation import ConceptRelation
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept
from app.models.knowledge_source import KnowledgeDocument, KnowledgeChunk


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


def document_response(document: KnowledgeDocument, chunk_count: int = 0) -> dict:
    return {"id": document.id, "title": document.title, "course": document.course, "chapter": document.chapter,
            "source_uri": document.source_uri, "review_status": document.review_status, "chunk_count": chunk_count,
            "created_at": document.created_at.isoformat() if document.created_at else None}


@router.post("/documents")
def create_document(payload: dict, db: Session = Depends(get_db)):
    title = str(payload.get("title", "")).strip()
    course = str(payload.get("course", "")).strip()
    if not title or not course:
        raise HTTPException(status_code=422, detail="title 和 course 不能为空")
    document = KnowledgeDocument(title=title, course=course, chapter=payload.get("chapter"), source_uri=payload.get("source_uri"), review_status=payload.get("review_status", "draft"))
    db.add(document)
    db.flush()
    for item in payload.get("chunks", []) or []:
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        db.add(KnowledgeChunk(document_id=document.id, concept_id=item.get("concept_id"), page_start=item.get("page_start"), page_end=item.get("page_end"), heading=item.get("heading"), chunk_type=item.get("chunk_type", "explanation"), content=content, review_status=item.get("review_status", "unreviewed")))
    db.commit()
    db.refresh(document)
    return document_response(document, db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).count())


@router.get("/documents")
def list_documents(course: str | None = None, db: Session = Depends(get_db)):
    query = db.query(KnowledgeDocument)
    if course:
        query = query.filter(KnowledgeDocument.course == course)
    documents = query.order_by(KnowledgeDocument.id.desc()).all()
    return {"items": [document_response(item, db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == item.id).count()) for item in documents]}


@router.get("/chunks/search")
def search_knowledge_chunks(q: str = Query(default="", max_length=200), course: str | None = None, chapter: str | None = None,
                            chunk_type: str | None = None, offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
                            db: Session = Depends(get_db)):
    query = db.query(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter((KnowledgeChunk.content.ilike(pattern)) | (KnowledgeChunk.heading.ilike(pattern)))
    if course:
        query = query.filter(KnowledgeDocument.course == course)
    if chapter:
        query = query.filter(KnowledgeDocument.chapter == chapter)
    if chunk_type:
        query = query.filter(KnowledgeChunk.chunk_type == chunk_type)
    total = query.count()
    rows = query.order_by(KnowledgeDocument.id.desc(), KnowledgeChunk.page_start.asc(), KnowledgeChunk.id.asc()).offset(offset).limit(limit).all()
    return {"query": q.strip(), "offset": offset, "limit": limit, "total": total, "items": [
        {"id": chunk.id, "document_id": document.id, "document_title": document.title, "course": document.course, "chapter": document.chapter,
         "concept_id": chunk.concept_id, "page_start": chunk.page_start, "page_end": chunk.page_end, "heading": chunk.heading,
         "chunk_type": chunk.chunk_type, "review_status": chunk.review_status, "content": chunk.content}
        for chunk, document in rows
    ]}


@router.get("/concepts/{concept_id}/sources")
def concept_sources(concept_id: int, db: Session = Depends(get_db)):
    if db.query(Concept).filter(Concept.id == concept_id).first() is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    rows = db.query(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id).filter(KnowledgeChunk.concept_id == concept_id).order_by(KnowledgeChunk.page_start.asc(), KnowledgeChunk.id.asc()).all()
    return {"concept_id": concept_id, "items": [{"chunk_id": chunk.id, "document_id": document.id, "document_title": document.title, "course": document.course, "chapter": document.chapter, "page_start": chunk.page_start, "page_end": chunk.page_end, "heading": chunk.heading, "chunk_type": chunk.chunk_type, "review_status": chunk.review_status, "content": chunk.content} for chunk, document in rows]}


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

    # 4. 其他关系（保留完整关系类型，兼容旧版 related）
    related_relations = db.query(
        ConceptRelation
    ).filter(
        (
            (ConceptRelation.source_concept_id == concept.id)
            |
            (ConceptRelation.target_concept_id == concept.id)
        ),
        ConceptRelation.relation.notin_(["prerequisite", "supports"]),
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
                "relation": relation.relation,
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
