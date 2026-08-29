from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.ai.analyzer import analyze_problem
from app.ai.concept_matcher import (
    find_similar_concepts,
    semantic_match
)

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

    # ==================================================
    # 1. 查找题目
    # ==================================================

    problem = db.query(Problem).filter(
        Problem.id == request.problem_id
    ).first()

    if problem is None:

        raise HTTPException(
            status_code=404,
            detail="Problem not found"
        )


    # ==================================================
    # 2. 调用 DeepSeek 分析题目
    # ==================================================

    result = analyze_problem(
        problem.content
    )

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
    # 3. 创建 / 复用 Concept
    # ==================================================

    for item in concepts_result:

        name = item.get("name")

        if not name:
            continue


        # ------------------------------------------------
        # 3.1 精确名称匹配
        # ------------------------------------------------

        concept = db.query(
            Concept
        ).filter(
            Concept.name == name
        ).first()


        # ------------------------------------------------
        # 3.2 如果不存在，进行语义匹配
        # ------------------------------------------------

        if concept is None:

            candidates = find_similar_concepts(
                db,
                name
            )

            concept = None


            # 只检查最相似的前 3 个候选
            for candidate in candidates[:3]:

                candidate_concept = candidate[
                    "concept"
                ]

                match_result = semantic_match(
                    name,
                    candidate_concept.name
                )


                # DeepSeek 判断为同一个概念
                if (
                    match_result.get("same") is True
                    and
                    match_result.get(
                        "confidence",
                        0
                    ) >= 0.85
                ):

                    concept = candidate_concept

                    break


        # ------------------------------------------------
        # 3.3 没有找到相同概念 → 创建
        # ------------------------------------------------

        if concept is None:

            concept = Concept(
                name=name,
                description=item.get(
                    "description"
                ),
                field=item.get(
                    "field"
                ),
                level=item.get(
                    "level",
                    1
                ),
                type=item.get(
                    "type",
                    "concept"
                )
            )

            db.add(concept)

            db.flush()


        # ------------------------------------------------
        # 3.4 保存返回结果
        # ------------------------------------------------

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
        # 4. 创建 ProblemConcept
        # ==================================================

        existing_problem_concept = db.query(
            ProblemConcept
        ).filter(

            ProblemConcept.problem_id
            == problem.id,

            ProblemConcept.concept_id
            == concept.id

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

            db.add(
                problem_concept
            )


    # ==================================================
    # 5. 建立知识点名称 → Concept ID
    # ==================================================

    concept_map = {}


    for item in concepts_result:

        name = item.get("name")

        if not name:
            continue


        # ------------------------------------------------
        # 精确查询
        # ------------------------------------------------

        concept = db.query(
            Concept
        ).filter(
            Concept.name == name
        ).first()


        # ------------------------------------------------
        # 如果名称发生了语义合并，
        # 这里重新寻找最匹配的 Concept
        # ------------------------------------------------

        if concept is None:

            candidates = find_similar_concepts(
                db,
                name
            )

            for candidate in candidates[:3]:

                candidate_concept = candidate[
                    "concept"
                ]

                match_result = semantic_match(
                    name,
                    candidate_concept.name
                )

                if (
                    match_result.get(
                        "same"
                    ) is True
                    and
                    match_result.get(
                        "confidence",
                        0
                    ) >= 0.85
                ):

                    concept = candidate_concept

                    break


        if concept is not None:

            concept_map[
                name
            ] = concept.id


    # ==================================================
    # 6. 创建 ConceptRelation
    # ==================================================

    created_relations = []


    for item in relations_result:

        source_name = item.get(
            "source"
        )

        target_name = item.get(
            "target"
        )

        relation_type = item.get(
            "relation",
            "related"
        )

        weight = item.get(
            "weight",
            1.0
        )


        # ------------------------------------------------
        # source / target 不存在
        # ------------------------------------------------

        if (
            source_name not in concept_map
            or
            target_name not in concept_map
        ):

            continue


        source_id = concept_map[
            source_name
        ]

        target_id = concept_map[
            target_name
        ]


        # ------------------------------------------------
        # 防止自己指向自己
        # ------------------------------------------------

        if source_id == target_id:

            continue


        # ------------------------------------------------
        # 检查关系是否已经存在
        # ------------------------------------------------

        existing_relation = db.query(
            ConceptRelation
        ).filter(

            ConceptRelation.source_concept_id
            == source_id,

            ConceptRelation.target_concept_id
            == target_id,

            ConceptRelation.relation
            == relation_type

        ).first()


        # ------------------------------------------------
        # 创建关系
        # ------------------------------------------------

        if existing_relation is None:

            concept_relation = ConceptRelation(

                source_concept_id=source_id,

                target_concept_id=target_id,

                relation=relation_type,

                weight=weight

            )

            db.add(
                concept_relation
            )


            created_relations.append({

                "source": source_name,

                "target": target_name,

                "relation": relation_type,

                "weight": weight

            })


    # ==================================================
    # 7. 提交数据库
    # ==================================================

    db.commit()


    # ==================================================
    # 8. 返回结果
    # ==================================================

    return {

        "problem_id": problem.id,

        "concepts": created_concepts,

        "relations": created_relations

    }