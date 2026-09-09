import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openai import (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    APIStatusError,
)

from app.database import SessionLocal
from app.models.concept import Concept
from app.models.concept_relation import ConceptRelation
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept

from app.ai.analyzer import client
from app.ai.concept_matcher import (
    semantic_retrieve_concepts,
    search_similar_problems,
)


router = APIRouter(
    prefix="/ai",
    tags=["AI"]
)


class AskRequest(BaseModel):
    question: str


# ============================================================
# Database
# ============================================================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# ============================================================
# DeepSeek API helper
# ============================================================

def call_deepseek(
    messages,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    response_format=None,
):
    """
    调用 DeepSeek API。

    主要解决：
    - APIConnectionError
    - incomplete chunked read
    - APITimeoutError
    - RateLimitError
    - 部分 5xx 错误

    自动重试。
    """

    last_error = None

    for attempt in range(max_retries):
        try:
            kwargs = {
                "model": "deepseek-v4-pro",
                "messages": messages,
            }

            if response_format is not None:
                kwargs["response_format"] = response_format

            response = client.chat.completions.create(
                **kwargs
            )

            if (
                response.choices
                and response.choices[0].message
                and response.choices[0].message.content
            ):
                return response.choices[0].message.content

            raise RuntimeError(
                "DeepSeek 返回了空响应。"
            )

        except (
            APIConnectionError,
            APITimeoutError,
            RateLimitError,
        ) as exc:

            last_error = exc

            if attempt < max_retries - 1:
                time.sleep(
                    retry_delay * (attempt + 1)
                )
                continue

            break

        except APIStatusError as exc:

            last_error = exc

            # 只有服务器错误才值得重试
            if exc.status_code >= 500:
                if attempt < max_retries - 1:
                    time.sleep(
                        retry_delay * (attempt + 1)
                    )
                    continue

            break

        except Exception as exc:

            last_error = exc

            # 未知错误不无限重试
            break

    if last_error is not None:
        raise last_error

    raise RuntimeError(
        "DeepSeek API 调用失败。"
    )


# ============================================================
# Safe AI retrieval
# ============================================================

def safe_semantic_retrieve_concepts(
    db: Session,
    question: str
):
    """
    知识点语义检索。

    semantic_retrieve_concepts() 当前返回：

    [
        {
            "concept": Concept对象,
            "similarity": 0.95,
            "reason": "..."
        }
    ]

    如果 DeepSeek 暂时不可用，
    不让整个请求直接崩溃。
    """

    try:
        return semantic_retrieve_concepts(
            db,
            question
        )

    except Exception as exc:
        print(
            "[AI] semantic concept retrieval failed:",
            repr(exc)
        )

        return []


def safe_search_similar_problems(
    db: Session,
    question: str,
    concept_ids: list[int],
):
    """
    历史相似题目检索。

    如果语义排序 API 失败，
    至少返回基于知识点召回的历史题目。
    """

    try:
        return search_similar_problems(
            db=db,
            question=question,
            concept_ids=concept_ids,
            candidate_limit=10,
            result_limit=5
        )

    except Exception as exc:
        print(
            "[AI] similar problem search failed:",
            repr(exc)
        )

        # ----------------------------------------------------
        # 降级策略：
        # 直接根据知识点找历史题目
        # ----------------------------------------------------

        if not concept_ids:
            return []

        problems = (
            db.query(
                Problem,
                ProblemConcept
            )
            .join(
                ProblemConcept,
                Problem.id
                == ProblemConcept.problem_id
            )
            .filter(
                ProblemConcept.concept_id.in_(
                    concept_ids
                )
            )
            .order_by(
                ProblemConcept.importance.desc()
            )
            .limit(5)
            .all()
        )

        results = []

        for problem, relation in problems:

            results.append({
                "id": problem.id,
                "title": problem.title,
                "content": problem.content,
                "solution": problem.solution,
                "difficulty": problem.difficulty,
                "score": relation.importance or 0,
                "similarity": None,
                "reason": "基于相关知识点召回"
            })

        return results


# ============================================================
# Knowledge graph
# ============================================================

def build_knowledge_graph(
    db: Session,
    matched_concepts
):
    """
    根据当前问题匹配到的知识点，
    展开一层知识图谱。

    matched_concepts 的结构：

    [
        {
            "concept": Concept对象,
            "similarity": ...,
            "reason": ...
        }
    ]
    """

    graph_nodes = []
    graph_relations = []

    visited_concepts = set()
    relation_keys = set()

    # --------------------------------------------------------
    # 第一层：直接匹配知识点
    # --------------------------------------------------------

    for item in matched_concepts:

        concept = item["concept"]

        if concept.id in visited_concepts:
            continue

        graph_nodes.append({
            "id": concept.id,
            "name": concept.name,
            "type": concept.type,
            "description": concept.description,
            "field": concept.field,
            "level": concept.level
        })

        visited_concepts.add(
            concept.id
        )

    # --------------------------------------------------------
    # 第二层：展开关系
    # --------------------------------------------------------

    for item in matched_concepts:

        concept = item["concept"]

        relations = (
            db.query(ConceptRelation)
            .filter(
                (
                    (
                        ConceptRelation.source_concept_id
                        == concept.id
                    )
                    |
                    (
                        ConceptRelation.target_concept_id
                        == concept.id
                    )
                )
            )
            .all()
        )

        for relation in relations:

            source = (
                db.query(Concept)
                .filter(
                    Concept.id
                    == relation.source_concept_id
                )
                .first()
            )

            target = (
                db.query(Concept)
                .filter(
                    Concept.id
                    == relation.target_concept_id
                )
                .first()
            )

            if source is None or target is None:
                continue

            relation_key = (
                source.id,
                target.id,
                relation.relation
            )

            if relation_key in relation_keys:
                continue

            relation_keys.add(
                relation_key
            )

            # ----------------------------------------------
            # source node
            # ----------------------------------------------

            if source.id not in visited_concepts:

                graph_nodes.append({
                    "id": source.id,
                    "name": source.name,
                    "type": source.type,
                    "description": source.description,
                    "field": source.field,
                    "level": source.level
                })

                visited_concepts.add(
                    source.id
                )

            # ----------------------------------------------
            # target node
            # ----------------------------------------------

            if target.id not in visited_concepts:

                graph_nodes.append({
                    "id": target.id,
                    "name": target.name,
                    "type": target.type,
                    "description": target.description,
                    "field": target.field,
                    "level": target.level
                })

                visited_concepts.add(
                    target.id
                )

            # ----------------------------------------------
            # relation
            # ----------------------------------------------

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

    return graph_nodes, graph_relations


# ============================================================
# Historical problems
# ============================================================

def get_historical_problems(
    db: Session,
    matched_concepts,
    limit: int = 10
):
    """
    根据知识点召回历史题目。

    一个题目可能关联多个知识点。
    """

    historical_problems = {}

    for item in matched_concepts:

        concept = item["concept"]

        problem_relations = (
            db.query(ProblemConcept)
            .filter(
                ProblemConcept.concept_id
                == concept.id
            )
            .all()
        )

        for relation in problem_relations:

            problem = (
                db.query(Problem)
                .filter(
                    Problem.id
                    == relation.problem_id
                )
                .first()
            )

            if problem is None:
                continue

            importance = (
                relation.importance
                if relation.importance is not None
                else 0
            )

            if problem.id not in historical_problems:

                historical_problems[
                    problem.id
                ] = {
                    "id": problem.id,
                    "title": problem.title,
                    "content": problem.content,
                    "solution": problem.solution,
                    "difficulty": problem.difficulty,
                    "importance": importance,
                    "matched_concepts": []
                }

            else:

                # 一个题目如果关联多个知识点，
                # 使用最高的重要程度

                historical_problems[
                    problem.id
                ]["importance"] = max(
                    historical_problems[
                        problem.id
                    ]["importance"],
                    importance
                )

            historical_problems[
                problem.id
            ]["matched_concepts"].append({
                "concept_id": concept.id,
                "concept_name": concept.name,
                "importance": importance
            })

    # --------------------------------------------------------
    # 按重要程度排序
    # --------------------------------------------------------

    problems = sorted(
        historical_problems.values(),
        key=lambda item: item["importance"],
        reverse=True
    )

    return problems[:limit]


# ============================================================
# Format historical problems
# ============================================================

def format_historical_problems(
    problems,
    max_items: int = 8,
    max_content_length: int = 1500,
    max_solution_length: int = 2500,
):
    """
    将历史题目压缩成 Prompt。

    防止历史数据过多导致：
    - Prompt 太长
    - API 响应慢
    - connection closed
    """

    if not problems:
        return "暂无相关历史题目。"

    text_parts = []

    for problem in problems[:max_items]:

        content = problem.get(
            "content"
        ) or ""

        solution = problem.get(
            "solution"
        ) or ""

        content = content[
            :max_content_length
        ]

        solution = solution[
            :max_solution_length
        ]

        matched_names = ", ".join(
            item["concept_name"]
            for item in problem.get(
                "matched_concepts",
                []
            )
        )

        text_parts.append(
            f"""
题目 ID：
{problem["id"]}

题目：
{problem["title"]}

题目内容：
{content}

已有解答：
{solution}

难度：
{problem["difficulty"]}

知识点重要程度：
{problem["importance"]}

相关知识点：
{matched_names}

------------------------------
"""
        )

    return "\n".join(
        text_parts
    )


# ============================================================
# Format similar problems
# ============================================================

def format_similar_problems(
    problems,
    max_items: int = 5,
    max_content_length: int = 1500,
    max_solution_length: int = 2500,
):
    """
    将相似题目压缩成 Prompt。
    """

    if not problems:
        return "暂无高度相似的历史题目。"

    text_parts = []

    for problem in problems[:max_items]:

        content = (
            problem.get("content")
            or ""
        )

        solution = (
            problem.get("solution")
            or ""
        )

        content = content[
            :max_content_length
        ]

        solution = solution[
            :max_solution_length
        ]

        text_parts.append(
            f"""
历史相似题 ID：
{problem["id"]}

题目：
{problem["title"]}

题目内容：
{content}

已有解答：
{solution}

难度：
{problem.get("difficulty")}

知识点召回分数：
{problem.get("score")}

语义相似度：
{problem.get("similarity")}

相似原因：
{problem.get("reason")}

------------------------------
"""
        )

    return "\n".join(
        text_parts
    )


# ============================================================
# Format graph
# ============================================================

def format_graph_nodes(
    graph_nodes
):
    if not graph_nodes:
        return "暂无相关知识图谱信息。"

    text_parts = []

    for node in graph_nodes:

        text_parts.append(
            f"""
知识点：
{node["name"]}

类型：
{node["type"]}

描述：
{node["description"]}

领域：
{node["field"]}

层级：
{node["level"]}

"""
        )

    return "\n".join(
        text_parts
    )


def format_graph_relations(
    graph_relations
):
    if not graph_relations:
        return "暂无相关知识关系。"

    text_parts = []

    for relation in graph_relations:

        text_parts.append(
            f"""
{relation["source"]["name"]}
   -- {relation["relation"]} -->
{relation["target"]["name"]}

权重：
{relation["weight"]}

"""
        )

    return "\n".join(
        text_parts
    )


# ============================================================
# Main AI endpoint
# ============================================================

@router.post("/ask")
def ask(
    request: AskRequest,
    db: Session = Depends(get_db)
):
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="问题不能为空。"
        )

    # ========================================================
    # 1. 语义检索知识点
    # ========================================================

    matched_concepts = (
        safe_semantic_retrieve_concepts(
            db,
            question
        )
    )

    # --------------------------------------------------------
    # semantic_retrieve_concepts() 返回的是：
    #
    # {
    #     "concept": Concept,
    #     "similarity": ...,
    #     "reason": ...
    # }
    #
    # 因此这里必须取 item["concept"].id
    # --------------------------------------------------------

    concept_ids = [
        item["concept"].id
        for item in matched_concepts
    ]

    # ========================================================
    # 2. 历史题目召回
    # ========================================================

    historical_problems = (
        get_historical_problems(
            db=db,
            matched_concepts=matched_concepts,
            limit=10
        )
    )

    # ========================================================
    # 3. 历史相似题目
    # ========================================================

    similar_problems = (
        safe_search_similar_problems(
            db=db,
            question=question,
            concept_ids=concept_ids
        )
    )

    # ========================================================
    # 4. 构建知识图谱
    # ========================================================

    (
        graph_nodes,
        graph_relations
    ) = build_knowledge_graph(
        db,
        matched_concepts
    )

    # ========================================================
    # 5. 格式化 Prompt 数据
    # ========================================================

    graph_text = format_graph_nodes(
        graph_nodes
    )

    relation_text = format_graph_relations(
        graph_relations
    )

    historical_problem_text = (
        format_historical_problems(
            historical_problems
        )
    )

    similar_problem_text = (
        format_similar_problems(
            similar_problems
        )
    )

    # ========================================================
    # 6. 最终数学回答 Prompt
    # ========================================================

    prompt = f"""
你是一名专业的数学知识助手。

你的任务是回答用户提出的数学问题。

============================================================
用户问题
============================================================

{question}

============================================================
一、当前问题相关知识点
============================================================

{graph_text}

============================================================
二、知识点之间的关系
============================================================

{relation_text}

============================================================
三、历史题目与已有解答
============================================================

{historical_problem_text}

============================================================
四、历史相似题目
============================================================

{similar_problem_text}

============================================================
回答要求
============================================================

1. 首先直接回答用户的问题。

2. 如果用户要求证明，
   必须给出完整、严谨的数学证明。

3. 可以参考历史题目和已有解答，
   但必须根据当前问题重新进行数学推导。

4. 不要机械复制历史题目的答案。

5. 历史解答只是参考资料。
   如果历史解答存在错误、不完整或不严谨，
   必须根据严格的数学推理进行修正。

6. 如果历史题目与当前问题高度相似，
   可以借鉴其证明思路，
   但必须根据当前问题重新组织答案。

7. 不要声称自己做过不存在的历史题目。

8. 不要创造数据库中不存在的历史题目、
   历史解答或知识点。

9. 如果使用知识图谱中的定理、性质或方法，
   可以自然地解释它们在当前问题中的作用。

10. 数学证明应优先使用定义、定理和严格的逻辑推导。

11. 对于拓扑学问题，
    特别注意区分：

    - 集合
    - 拓扑空间
    - 映射
    - 像
    - 原像
    - 开集
    - 开覆盖
    - 有限子覆盖
    - 紧性
    - 紧集

12. 不要为了使用知识图谱而强行加入无关知识。

13. 如果当前问题和历史题目高度相似，
    可以指出两者之间的联系，
    但不要虚构用户曾经做过某道题。

14. 回答应当具有数学教材级别的严谨性，
    同时尽量让学生能够理解证明为什么成立。

15. 如果问题存在数学上的歧义，
    应先说明采用的定义或解释。

16. 历史题目和相似题目只是辅助材料，
    不能把它们当作数学事实。

17. 如果知识图谱中的关系与严格数学推理冲突，
    以严格数学推理为准。

18. 如果当前问题可以由某个定理直接解决，
    应明确指出所使用的定理。

19. 如果给出证明，
    应尽量按照：

    定义
    → 已知条件
    → 关键定理
    → 推导
    → 结论

    的结构组织。

20. 不要输出与问题无关的大段知识背景。

请直接用中文回答。
"""

    # ========================================================
    # 7. 最终 DeepSeek 调用
    # ========================================================

    try:

        answer = call_deepseek(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一名专业、严谨的数学知识助手，"
                        "擅长数学证明、数学知识图谱、"
                        "历史题目检索和数学题目分析。"
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_retries=3,
            retry_delay=2.0
        )

    except Exception as exc:

        print(
            "[AI] final answer generation failed:",
            repr(exc)
        )

        # ----------------------------------------------------
        # 不再直接返回 Python 500 traceback。
        # 返回明确的 API 错误。
        # ----------------------------------------------------

        raise HTTPException(
            status_code=503,
            detail=(
                "DeepSeek 当前暂时无法完成回答。"
                "知识点和历史题目检索已经完成，"
                "请稍后重新提交。"
            )
        )

    # ========================================================
    # 8. 返回完整结果
    # ========================================================

    return {
        "question": question,

        "answer": answer,

        "concepts": [
            {
                "id": item["concept"].id,
                "name": item["concept"].name,
                "type": item["concept"].type,
                "similarity": item.get("similarity"),
                "reason": item.get("reason", "")
            }
            for item in matched_concepts
        ],

        "historical_problems": [
            {
                "id": problem["id"],
                "title": problem["title"],
                "content": problem["content"],
                "solution": problem["solution"],
                "difficulty": problem["difficulty"],
                "importance": problem["importance"],
                "matched_concepts": (
                    problem["matched_concepts"]
                )
            }
            for problem in historical_problems
        ],

        "similar_problems": similar_problems,

        "knowledge_graph": {
            "nodes": graph_nodes,
            "relations": graph_relations
        }
    }