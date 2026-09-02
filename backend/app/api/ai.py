from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal

from app.ai.analyzer import analyze_problem, client
from app.ai.concept_matcher import (
    resolve_concept,
    validate_relation,
    semantic_retrieve_concepts
)

from app.schemas.ai import ProblemAnalysisRequest
from app.schemas.ask import AskRequest

from app.models.problem import Problem
from app.models.concept import Concept
from app.models.problem_concept import ProblemConcept
from app.models.concept_relation import ConceptRelation


router = APIRouter(prefix="/ai", tags=["AI"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# AI：分析数学题目
# ============================================================

@router.post("/analyze-problem")
def analyze_math_problem(
    request: ProblemAnalysisRequest,
    db: Session = Depends(get_db)
):
    problem = db.query(Problem).filter(
        Problem.id == request.problem_id
    ).first()

    if problem is None:
        raise HTTPException(
            status_code=404,
            detail="Problem not found"
        )

    # --------------------------------------------------------
    # 1. DeepSeek 分析题目
    # --------------------------------------------------------

    result = analyze_problem(problem.content)

    concepts_result = result.get("concepts", [])
    relations_result = result.get("relations", [])

    created_concepts = []
    concept_map = {}

    # --------------------------------------------------------
    # 2. 创建 / 匹配知识点
    # --------------------------------------------------------

    for item in concepts_result:

        name = item.get("name")

        if not name:
            continue

        concept = resolve_concept(
            db,
            name
        )

        # 如果数据库不存在，则创建
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

        concept_map[name] = concept.id

        created_concepts.append({
            "id": concept.id,
            "name": concept.name,
            "type": concept.type,
            "importance": item.get(
                "importance",
                1.0
            )
        })

        # ----------------------------------------------------
        # 建立 Problem -> Concept
        # ----------------------------------------------------

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

    # --------------------------------------------------------
    # 3. 建立 Concept -> Concept 关系
    # --------------------------------------------------------

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

        if not source_name or not target_name:
            continue

        # 禁止自己指向自己
        if source_name == target_name:
            continue

        # 只允许这三种关系
        if relation_type not in {
            "prerequisite",
            "supports",
            "related"
        }:
            continue

        # weight 类型检查
        if not isinstance(weight, (int, float)):
            weight = 1.0

        # 限制在 0~1
        weight = max(
            0.0,
            min(1.0, weight)
        )

        # ----------------------------------------------------
        # 找 source
        # ----------------------------------------------------

        source_concept = resolve_concept(
            db,
            source_name
        )

        # ----------------------------------------------------
        # 找 target
        # ----------------------------------------------------

        target_concept = resolve_concept(
            db,
            target_name
        )

        if source_concept is None:
            continue

        if target_concept is None:
            continue

        # 禁止自己指向自己
        if source_concept.id == target_concept.id:
            continue

        # ----------------------------------------------------
        # DeepSeek 二次验证关系
        # ----------------------------------------------------

        validation = validate_relation(
            source_concept.name,
            target_concept.name,
            relation_type
        )

        if validation.get("valid") is not True:
            continue

        if validation.get(
            "confidence",
            0
        ) < 0.85:
            continue

        # ----------------------------------------------------
        # 检查数据库中是否已经存在
        # ----------------------------------------------------

        existing_relation = db.query(
            ConceptRelation
        ).filter(
            ConceptRelation.source_concept_id
            == source_concept.id,

            ConceptRelation.target_concept_id
            == target_concept.id,

            ConceptRelation.relation
            == relation_type
        ).first()

        if existing_relation is None:

            concept_relation = ConceptRelation(
                source_concept_id=source_concept.id,
                target_concept_id=target_concept.id,
                relation=relation_type,
                weight=weight
            )

            db.add(concept_relation)

            created_relations.append({
                "source": source_concept.name,
                "target": target_concept.name,
                "relation": relation_type,
                "weight": weight
            })

    # --------------------------------------------------------
    # 4. 提交数据库
    # --------------------------------------------------------

    db.commit()

    return {
        "problem_id": problem.id,
        "concepts": created_concepts,
        "relations": created_relations
    }


# ============================================================
# AI：数学问答
# ============================================================

@router.post("/ask")
def ask_question(
    request: AskRequest,
    db: Session = Depends(get_db)
):
    """
    根据用户问题：

    1. 使用 DeepSeek 进行语义检索
    2. 找到核心知识点
    3. 沿知识图谱扩展
    4. 获取前置知识
    5. 获取支撑知识
    6. 获取相关知识
    7. 获取相关题目
    8. 将知识图谱上下文交给 DeepSeek
    9. 生成最终数学回答
    """

    # --------------------------------------------------------
    # 1. 获取用户问题
    # --------------------------------------------------------

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty"
        )

    # --------------------------------------------------------
    # 2. 使用 DeepSeek 进行语义检索
    # --------------------------------------------------------

    matched_concepts = semantic_retrieve_concepts(
        db,
        question
    )

    # --------------------------------------------------------
    # 3. 如果没有找到知识点
    # --------------------------------------------------------

    if not matched_concepts:
        return {
            "question": question,
            "answer": "暂时没有在知识图谱中找到相关知识点。",
            "concepts": [],
            "knowledge_graph": {
                "nodes": [],
                "relations": []
            }
        }

    # --------------------------------------------------------
    # 4. 沿知识图谱扩展
    # --------------------------------------------------------

    expanded_concepts = {}

    for concept in matched_concepts:

        # 当前核心知识点
        expanded_concepts[concept.id] = concept

        # ----------------------------------------------------
        # 找到与当前知识点直接相连的关系
        # ----------------------------------------------------

        relations = db.query(
            ConceptRelation
        ).filter(
            (
                (ConceptRelation.source_concept_id == concept.id)
                |
                (ConceptRelation.target_concept_id == concept.id)
            )
        ).all()

        # ----------------------------------------------------
        # 加入关系另一端的知识点
        # ----------------------------------------------------

        for relation in relations:

            if relation.source_concept_id == concept.id:
                other_id = relation.target_concept_id
            else:
                other_id = relation.source_concept_id

            other = db.query(
                Concept
            ).filter(
                Concept.id == other_id
            ).first()

            if other is not None:
                expanded_concepts[other.id] = other

    # --------------------------------------------------------
    # 限制扩展后的知识点数量
    # --------------------------------------------------------

    expanded_concepts = dict(
        list(expanded_concepts.items())[:10]
    )

    # --------------------------------------------------------
    # 5. 构造知识图谱上下文
    # --------------------------------------------------------

    knowledge_context = []

    for concept in expanded_concepts.values():

        # ====================================================
        # 前置知识
        # ====================================================

        prerequisite_relations = db.query(
            ConceptRelation
        ).filter(
            ConceptRelation.target_concept_id == concept.id,
            ConceptRelation.relation == "prerequisite"
        ).all()

        prerequisites = []

        for relation in prerequisite_relations:

            source = db.query(
                Concept
            ).filter(
                Concept.id == relation.source_concept_id
            ).first()

            if source:
                prerequisites.append({
                    "name": source.name,
                    "weight": relation.weight
                })

        # ====================================================
        # 支撑知识
        # ====================================================

        support_relations = db.query(
            ConceptRelation
        ).filter(
            ConceptRelation.target_concept_id == concept.id,
            ConceptRelation.relation == "supports"
        ).all()

        supports = []

        for relation in support_relations:

            source = db.query(
                Concept
            ).filter(
                Concept.id == relation.source_concept_id
            ).first()

            if source:
                supports.append({
                    "name": source.name,
                    "weight": relation.weight
                })

        # ====================================================
        # Related 知识
        # ====================================================

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

            other = db.query(
                Concept
            ).filter(
                Concept.id == other_id
            ).first()

            if other:
                related.append({
                    "name": other.name,
                    "weight": relation.weight
                })

        # ====================================================
        # 相关题目
        # ====================================================

        problem_relations = db.query(
            ProblemConcept
        ).filter(
            ProblemConcept.concept_id == concept.id
        ).all()

        problems = []

        for relation in problem_relations:

            problem = db.query(
                Problem
            ).filter(
                Problem.id == relation.problem_id
            ).first()

            if problem:
                problems.append({
                    "id": problem.id,
                    "title": problem.title,
                    "difficulty": problem.difficulty,
                    "importance": relation.importance
                })

        # ====================================================
        # 保存知识上下文
        # ====================================================

        knowledge_context.append({

            "id": concept.id,

            "name": concept.name,

            "type": concept.type,

            "description": concept.description,

            "field": concept.field,

            "level": concept.level,

            "prerequisites": prerequisites,

            "supports": supports,

            "related": related,

            "problems": problems
        })

    # --------------------------------------------------------
    # 6. 构造给 DeepSeek 的文本
    # --------------------------------------------------------

    context_text = ""

    for item in knowledge_context:

        prerequisite_text = ", ".join(
            prerequisite["name"]
            for prerequisite in item["prerequisites"]
        )

        supports_text = ", ".join(
            support["name"]
            for support in item["supports"]
        )

        related_text = ", ".join(
            related_item["name"]
            for related_item in item["related"]
        )

        problem_text = ", ".join(
            problem["title"]
            for problem in item["problems"]
        )

        context_text += f"""

==============================
知识点
==============================

ID：
{item["id"]}

名称：
{item["name"]}

类型：
{item["type"]}

领域：
{item["field"]}

层级：
{item["level"]}

定义 / 描述：
{item["description"]}

前置知识：
{prerequisite_text}

支撑知识：
{supports_text}

相关知识：
{related_text}

相关题目：
{problem_text}

"""

    # --------------------------------------------------------
    # 7. 构造 DeepSeek Prompt
    # --------------------------------------------------------

    prompt = f"""

你是一名专业、严谨的高等数学教师。

请回答用户的问题。

==============================
用户问题
==============================

{question}


==============================
数学知识图谱
==============================

{context_text}


==============================
回答要求
==============================

1. 优先使用知识图谱中的信息。

2. 知识图谱中的知识点、前置关系和支撑关系代表已经建立的数学知识网络。

3. 不要编造知识图谱中不存在的关系。

4. 如果知识图谱中的信息不足，可以使用你自己的数学知识补充。

5. 数学定义必须准确。

6. 如果用户要求证明，请给出完整、严谨、连续的证明。

7. 如果知识图谱中存在相关定理，应优先使用该定理解释问题。

8. 如果存在前置知识，应适当解释这些前置知识为什么出现。

9. 如果存在相关题目，可以参考这些题目的知识背景，但不要虚构题目内容。

10. 不要为了使用知识图谱而强行加入无关知识。

11. 使用中文回答。

12. 根据问题复杂程度控制回答长度。

13. 如果是证明题，优先给出：
    - 定义
    - 证明思路
    - 正式证明
    - 直观解释

14. 数学公式使用 LaTeX。

"""

    # --------------------------------------------------------
    # 8. 调用 DeepSeek
    # --------------------------------------------------------

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一名严谨的高等数学教师，"
                    "同时也是数学知识图谱推理专家。"
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    answer = response.choices[0].message.content

    # --------------------------------------------------------
    # 9. 构造知识图谱节点
    # --------------------------------------------------------

    graph_nodes = []

    for concept in expanded_concepts.values():

        graph_nodes.append({
            "id": concept.id,
            "name": concept.name,
            "type": concept.type,
            "description": concept.description,
            "field": concept.field,
            "level": concept.level
        })

    # --------------------------------------------------------
    # 10. 构造知识图谱关系
    # --------------------------------------------------------

    graph_relations = []

    concept_ids = set(
        expanded_concepts.keys()
    )

    relations = db.query(
        ConceptRelation
    ).all()

    for relation in relations:

        # 只保留当前知识图谱节点之间的关系
        if (
            relation.source_concept_id not in concept_ids
            or
            relation.target_concept_id not in concept_ids
        ):
            continue

        source = expanded_concepts.get(
            relation.source_concept_id
        )

        target = expanded_concepts.get(
            relation.target_concept_id
        )

        if source is None or target is None:
            continue

        graph_relations.append({

            "source": {
                "id": source.id,
                "name": source.name
            },

            "target": {
                "id": target.id,
                "name": target.name
            },

            "relation": relation.relation,

            "weight": relation.weight
        })

    # --------------------------------------------------------
    # 11. 返回最终结果
    # --------------------------------------------------------

    return {

        "question": question,

        "answer": answer,

        # AI 直接检索到的核心知识点
        "concepts": [

            {
                "id": concept.id,
                "name": concept.name,
                "type": concept.type
            }

            for concept in matched_concepts

        ],

        # 知识图谱
        "knowledge_graph": {

            "nodes": graph_nodes,

            "relations": graph_relations

        }

    }