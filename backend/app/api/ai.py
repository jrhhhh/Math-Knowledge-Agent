from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.ai.analyzer import analyze_problem
from app.schemas.ai import ProblemAnalysisRequest
from app.models.problem import Problem
from app.models.concept import Concept
from app.models.problem_concept import ProblemConcept
from app.models.concept_relation import ConceptRelation


router = APIRouter(
    prefix="/ai",
    tags=["AI"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/analyze-problem")
def analyze_math_problem(
    request: ProblemAnalysisRequest,
    db: Session = Depends(get_db)
):

    # 1. 查找题目
    problem = db.query(Problem).filter(
        Problem.id == request.problem_id
    ).first()

    if problem is None:
        raise HTTPException(
            status_code=404,
            detail="Problem not found"
        )

    # 2. 调用 DeepSeek
    result = analyze_problem(problem.content)

    concepts_result = result.get(
        "concepts",
        []
    )

    relations_result = result.get(
        "relations",
        []
    )

    created_concepts = []

    # ==================================================
    # 第一部分：创建 / 复用 Concept
    # ==================================================

    for item in concepts_result:

        name = item.get("name")

        if not name:
            continue

        # 查询已有知识点
        concept = db.query(Concept).filter(
            Concept.name == name
        ).first()

        # 如果不存在，创建
        if concept is None:

            concept = Concept(
                name=name,
                description=item.get("description"),
                field=item.get("field"),
                level=item.get("level", 1),
                type=item.get("type", "concept")
            )

            db.add(concept)
            db.flush()

        created_concepts.append({
            "id": concept.id,
            "name": concept.name,
            "type": concept.type,
            "importance": item.get(
                "importance",
                1.0
            )
        })

        # ==================================================
        # 第二部分：创建 ProblemConcept
        # ==================================================

        existing_problem_concept = db.query(
            ProblemConcept
        ).filter(
            ProblemConcept.problem_id == problem.id,
            ProblemConcept.concept_id == concept.id
        ).first()

        if existing_problem_concept is None:

            problem_concept = ProblemConcept(
                problem_id=problem.id,
                concept_id=concept.id,
                importance=item.get(
                    "importance",
                    1.0
                ),
                relation="related"
            )

            db.add(problem_concept)

    # ==================================================
    # 第三部分：建立知识点名称 → ID 的映射
    # ==================================================

    concept_map = {}

    for item in concepts_result:

        name = item.get("name")

        if not name:
            continue

        concept = db.query(Concept).filter(
            Concept.name == name
        ).first()

        if concept is not None:
            concept_map[name] = concept.id

    # ==================================================
    # 第四部分：创建 ConceptRelation
    # ==================================================

    created_relations = []

    for item in relations_result:

        source_name = item.get("source")
        target_name = item.get("target")
        relation_type = item.get(
            "relation",
            "related"
        )
        weight = item.get(
            "weight",
            1.0
        )

        # source 或 target 不存在，跳过
        if (
            source_name not in concept_map
            or target_name not in concept_map
        ):
            continue

        source_id = concept_map[source_name]
        target_id = concept_map[target_name]

        # 防止自己指向自己
        if source_id == target_id:
            continue

        # 检查关系是否已经存在
        existing_relation = db.query(
            ConceptRelation
        ).filter(
            ConceptRelation.source_concept_id == source_id,
            ConceptRelation.target_concept_id == target_id,
            ConceptRelation.relation == relation_type
        ).first()

        if existing_relation is None:

            concept_relation = ConceptRelation(
                source_concept_id=source_id,
                target_concept_id=target_id,
                relation=relation_type,
                weight=weight
            )

            db.add(concept_relation)

            created_relations.append({
                "source": source_name,
                "target": target_name,
                "relation": relation_type,
                "weight": weight
            })

    # ==================================================
    # 第五部分：提交数据库
    # ==================================================

    db.commit()

    return {
        "problem_id": problem.id,
        "concepts": created_concepts,
        "relations": created_relations
    }