from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.ai.analyzer import analyze_problem
from app.schemas.ai import ProblemAnalysisRequest
from app.models.problem import Problem
from app.models.concept import Concept
from app.models.problem_concept import ProblemConcept


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

    # 1. 检查题目是否存在
    problem = db.query(Problem).filter(
        Problem.id == request.problem_id
    ).first()

    if problem is None:
        raise HTTPException(
            status_code=404,
            detail="Problem not found"
        )

    # 2. 调用 DeepSeek 分析题目
    result = analyze_problem(problem.content)

    concepts_result = result.get(
        "concepts",
        []
    )

    created_concepts = []

    # 3. 处理每一个知识点
    for item in concepts_result:

        name = item.get("name")

        if not name:
            continue

        # 4. 查询数据库中是否已经存在
        concept = db.query(Concept).filter(
            Concept.name == name
        ).first()

        # 5. 不存在就创建
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

        # 6. 检查题目和知识点是否已经建立关系
        relation = db.query(ProblemConcept).filter(
            ProblemConcept.problem_id == problem.id,
            ProblemConcept.concept_id == concept.id
        ).first()

        # 7. 如果没有关系，就建立关系
        if relation is None:

            relation = ProblemConcept(
                problem_id=problem.id,
                concept_id=concept.id,
                importance=item.get(
                    "importance",
                    1.0
                ),
                relation="related"
            )

            db.add(relation)

        created_concepts.append({
            "id": concept.id,
            "name": concept.name,
            "type": concept.type,
            "importance": item.get(
                "importance",
                1.0
            )
        })

    # 8. 保存数据库
    db.commit()

    return {
        "problem_id": problem.id,
        "concepts": created_concepts
    }