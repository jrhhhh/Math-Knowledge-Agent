import json
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
    normalize_relation,
)


router = APIRouter(
    prefix="/ai",
    tags=["AI"]
)


class AskRequest(BaseModel):
    question: str


class RelatedGraphRequest(BaseModel):
    question: str


class ProofAnalyzeRequest(BaseModel):
    question: str
    proof: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/proof-analyze")
def analyze_proof(
    request: ProofAnalyzeRequest,
    db: Session = Depends(get_db),
):
    """分析用户证明的步骤、逻辑缺口和相关知识点。"""
    if not request.question.strip() or not request.proof.strip():
        raise HTTPException(status_code=422, detail="question 和 proof 不能为空。")

    matched = safe_semantic_retrieve_concepts(db, request.question)
    concept_context = [
        {
            "id": item["concept"].id,
            "name": item["concept"].name,
            "type": item["concept"].type,
            "similarity": item.get("similarity", 0.0),
        }
        for item in matched
    ]
    prompt = f"""
你是严格的数学证明审查助手。请分析下面的题目和用户证明。

题目：
{request.question}

用户证明：
{request.proof}

相关知识点候选：
{json.dumps(concept_context, ensure_ascii=False)}

将证明拆成有序步骤，检查每一步是否由前一步和已知条件推出。
错误类型只能使用：missing_assumption、invalid_inference、wrong_theorem、undefined_symbol、circular_reasoning、incomplete、none。
只返回 JSON：
{{
  "valid": true,
  "summary": "总体判断",
  "steps": [
    {{"step": 1, "text": "步骤内容", "status": "valid", "error_type": "none", "reason": "理由", "related_concepts": ["知识点"]}}
  ],
  "missing_assumptions": ["缺失条件"],
  "suggestions": ["改进建议"]
}}
"""
    try:
        raw = call_deepseek(
            messages=[
                {"role": "system", "content": "你是严谨的数学证明验证器，只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            max_retries=2,
            retry_delay=1.0,
            response_format={"type": "json_object"},
        )
        result = json.loads(raw)
    except Exception as exc:
        print("[AI] proof analysis failed:", repr(exc))
        raise HTTPException(status_code=503, detail="证明分析服务暂时不可用。")

    steps = result.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    normalized_steps = []
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            continue
        normalized_steps.append({
            "step": step.get("step", index),
            "text": str(step.get("text", "")),
            "status": step.get("status", "invalid"),
            "error_type": step.get("error_type", "incomplete"),
            "reason": str(step.get("reason", "")),
            "related_concepts": step.get("related_concepts", []),
        })
    return {
        "question": request.question,
        "valid": bool(result.get("valid", False)),
        "summary": str(result.get("summary", "")),
        "steps": normalized_steps,
        "missing_assumptions": result.get("missing_assumptions", []),
        "suggestions": result.get("suggestions", []),
        "matched_concepts": concept_context,
    }


# ============================================================
# DeepSeek API helper
# ============================================================

def call_deepseek(
    messages,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    response_format=None,
    max_tokens: int | None = None,
    timeout: float | None = None,
    extra_body: dict | None = None,
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

            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens

            if timeout is not None:
                kwargs["timeout"] = timeout

            if extra_body is not None:
                kwargs["extra_body"] = extra_body

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

    # 常见问题优先走本地匹配，避免为明显命中的知识点调用 LLM。
    normalized_question = "".join(question.lower().split())
    local_matches = []
    for concept in db.query(Concept).all():
        normalized_name = "".join((concept.name or "").lower().split())
        if normalized_name and normalized_name in normalized_question:
            local_matches.append({
                "concept": concept,
                "similarity": 1.0,
                "reason": "知识点名称在问题中直接出现。",
            })
    if local_matches:
        return local_matches[:5]

    # 短输入通常是“定理/概念名称”查询。若本地库未收录，直接交给
    # 数学回答模型比先等待一次全库语义检索更快，也不会丢失答案质量。
    if len(normalized_question) <= 20:
        print("[AI] skipping semantic retrieval for short unmatched query")
        return []

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
            result_limit=5,
            semantic=False,
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


@router.post("/related-graph")
def get_related_graph(
    request: RelatedGraphRequest,
    db: Session = Depends(get_db),
):
    """快速筛选并展开已有知识库中的一层相关图谱，不调用答案生成模型。"""
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空。")

    return generate_ai_related_graph(db, question)


def parse_ai_graph_json(raw: str):
    """解析普通文本通道中可能带有 Markdown 围栏的 JSON 图谱。"""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    return json.loads(text[start:end + 1])


def generate_ai_related_graph(db: Session, question: str):
    """由模型生成题目相关的临时知识图谱，并尽可能锚定到本地知识库。"""
    prompt = f"""为数学问题“{question}”生成学习知识图谱。只输出 JSON：
{{"nodes":[{{"id":"n1","name":"名称","type":"concept","description":"说明","field":"分支","level":1}}],"edges":[{{"source":"n1","target":"n2","relation":"prerequisite","weight":0.9}}]}}

给出 4-8 个中文节点和 3-12 条边。type 只能为 concept/theorem/property/method；
relation 只能为 prerequisite/supports/defines/property_of/uses/equivalent_to/generalizes/specializes。
边端点必须存在且不能自环。节点只保留解答该问题必须的定义、条件、定理或方法。"""

    try:
        raw = call_deepseek(
            messages=[
                {
                    "role": "system",
                    "content": "你是严谨的数学知识图谱构建器，只输出合法 JSON。",
                },
                {"role": "user", "content": prompt},
            ],
            max_retries=2,
            max_tokens=1600,
            timeout=45.0,
            # 图谱是结构化抽取任务，不需要消耗高强度推理预算；关闭默认
            # thinking 模式可避免 reasoning_content 挤占 JSON 正文。
            extra_body={"thinking": {"type": "disabled"}},
        )
        generated = parse_ai_graph_json(raw)
    except json.JSONDecodeError:
        # 某些推理轮次会在较长描述字段中截断。第二轮改用极简契约，
        # 仍完全由 AI 生成，只减少令牌与格式风险。
        compact_prompt = f"""为“{question}”输出一个数学知识图谱 JSON，不要解释：
{{"nodes":[{{"id":"n1","name":"概念","type":"concept"}}],"edges":[{{"source":"n1","target":"n2","relation":"uses","weight":0.9}}]}}
给 4-7 个节点和 3-10 条边。type 仅 concept/theorem/property/method；relation 仅 prerequisite/supports/defines/property_of/uses/equivalent_to/generalizes/specializes。"""
        try:
            raw = call_deepseek(
                messages=[
                    {"role": "system", "content": "你是数学知识图谱构建器，只输出完整合法 JSON。"},
                    {"role": "user", "content": compact_prompt},
                ],
                max_retries=2,
                max_tokens=1600,
                timeout=45.0,
                extra_body={"thinking": {"type": "disabled"}},
            )
            generated = parse_ai_graph_json(raw)
        except Exception as exc:
            print("[AI] compact related graph generation failed:", repr(exc))
            raise HTTPException(
                status_code=503,
                detail="DeepSeek 未能生成完整知识图谱，请稍后重试。",
            ) from exc
    except Exception as exc:
        print("[AI] related graph generation failed:", repr(exc))
        raise HTTPException(
            status_code=503,
            detail="DeepSeek 未能生成知识图谱，请稍后重试。",
        ) from exc

    valid_types = {"concept", "theorem", "property", "method"}
    generated_nodes = generated.get("nodes")
    if not isinstance(generated_nodes, list):
        raise HTTPException(status_code=502, detail="DeepSeek 返回的知识图谱格式无效。")

    database_concepts = db.query(Concept).all()
    by_normalized_name = {
        "".join((concept.name or "").lower().split()): concept
        for concept in database_concepts
    }
    nodes = []
    node_id_map = {}
    used_ids = set()
    matched_concepts = []

    for index, node in enumerate(generated_nodes[:10], start=1):
        if not isinstance(node, dict):
            continue
        source_id = str(node.get("id", "")).strip()
        name = str(node.get("name", "")).strip()[:48]
        node_type = str(node.get("type", "concept")).strip().lower()
        if not source_id or not name or source_id in node_id_map or node_type not in valid_types:
            continue

        normalized_name = "".join(name.lower().split())
        local_concept = by_normalized_name.get(normalized_name)
        if local_concept is not None:
            graph_id = local_concept.id
            matched_concepts.append({
                "concept": local_concept,
                "similarity": 1.0,
                "reason": "AI 图谱节点与本地知识点同名。",
            })
            node_data = {
                "id": graph_id,
                "name": local_concept.name,
                "type": local_concept.type,
                "description": local_concept.description,
                "field": local_concept.field,
                "level": local_concept.level,
                "source": "knowledge_base",
            }
        else:
            graph_id = f"ai-{index}"
            node_data = {
                "id": graph_id,
                "name": name,
                "type": node_type,
                "description": str(node.get("description", "")).strip()[:160],
                "field": str(node.get("field", "数学")).strip()[:32] or "数学",
                "level": max(1, min(5, int(node.get("level", 1)) if str(node.get("level", "")).isdigit() else 1)),
                "source": "ai_generated",
            }

        if graph_id in used_ids:
            node_id_map[source_id] = graph_id
            continue
        used_ids.add(graph_id)
        node_id_map[source_id] = graph_id
        nodes.append(node_data)

    if len(nodes) < 2:
        raise HTTPException(status_code=502, detail="DeepSeek 未返回足够的有效知识点，请重试。")

    edges = []
    edge_keys = set()
    for edge in generated.get("edges", [])[:14]:
        if not isinstance(edge, dict):
            continue
        source = node_id_map.get(str(edge.get("source", "")).strip())
        target = node_id_map.get(str(edge.get("target", "")).strip())
        relation = normalize_relation(edge.get("relation"))
        if source is None or target is None or source == target or relation is None:
            continue
        edge_key = (source, target, relation)
        if edge_key in edge_keys:
            continue
        edge_keys.add(edge_key)
        try:
            weight = max(0.0, min(1.0, float(edge.get("weight", 0.8))))
        except (TypeError, ValueError):
            weight = 0.8
        edges.append({"source": source, "target": target, "relation": relation, "weight": weight})

    # 已知节点额外展开真实数据库关系，使 AI 结果与既有知识库连通。
    local_nodes, local_relations = build_knowledge_graph(db, matched_concepts)
    known_node_ids = {node["id"] for node in nodes}
    for local_node in local_nodes:
        if local_node["id"] not in known_node_ids and len(nodes) < 16:
            local_node["source"] = "knowledge_base"
            nodes.append(local_node)
            known_node_ids.add(local_node["id"])
    for relation in local_relations:
        edge_key = (relation["source"]["id"], relation["target"]["id"], relation["relation"])
        if edge_key not in edge_keys:
            edge_keys.add(edge_key)
            edges.append({
                "source": relation["source"]["id"],
                "target": relation["target"]["id"],
                "relation": relation["relation"],
                "weight": relation.get("weight", 1.0),
            })

    return {
        "question": question,
        "concepts": [
            {"id": node["id"], "name": node["name"], "type": node["type"], "similarity": 1.0, "source": node["source"]}
            for node in nodes
        ],
        "knowledge_graph": {"nodes": nodes, "edges": edges},
        "message": "AI 已根据问题生成相关知识图谱。",
    }


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
    total_matched_concepts = len({item["concept"].id for item in matched_concepts})
    similarity_by_concept = {}
    for item in matched_concepts:
        try:
            similarity = float(item.get("similarity") or 0.0)
        except (TypeError, ValueError):
            similarity = 0.0
        similarity_by_concept[item["concept"].id] = max(0.0, min(1.0, similarity))

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

            matches = historical_problems[problem.id]["matched_concepts"]
            existing = next(
                (match for match in matches if match["concept_id"] == concept.id),
                None,
            )
            if existing is None:
                matches.append({
                    "concept_id": concept.id,
                    "concept_name": concept.name,
                    "importance": importance,
                    "similarity": similarity_by_concept.get(concept.id, 0.0),
                })
            else:
                existing["importance"] = max(existing["importance"], importance)

    for problem in historical_problems.values():
        matches = problem["matched_concepts"]
        matched_count = len(matches)
        coverage = matched_count / total_matched_concepts if total_matched_concepts else 0.0
        similarities = [match["similarity"] for match in matches]
        problem["coverage"] = round(coverage, 4)
        problem["score"] = round(
            max(similarities, default=0.0) * 0.45
            + coverage * 0.30
            + problem["importance"] * 0.15
            + (sum(similarities) / len(similarities) if similarities else 0.0) * 0.10,
            4,
        )

    # --------------------------------------------------------
    # 按综合相关程度排序
    # --------------------------------------------------------

    problems = sorted(
        historical_problems.values(),
        key=lambda item: (item["score"], item["importance"], item["id"]),
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
    started_at = time.perf_counter()
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
    print("[Timing] concept retrieval: %.2fs" % (time.perf_counter() - started_at))

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
    print("[Timing] historical retrieval: %.2fs" % (time.perf_counter() - started_at))

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
    print("[Timing] similar problems: %.2fs" % (time.perf_counter() - started_at))

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
    print("[Timing] graph build: %.2fs" % (time.perf_counter() - started_at))

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

    # 最终回答只带入高价值上下文，避免大 Prompt 导致生成超时。
    compact_prompt = f"""请用中文回答这个数学问题：

{question}

相关知识点：
{format_graph_nodes(graph_nodes[:6])}

关键关系：
{format_graph_relations(graph_relations[:10])}

可参考历史题：
{format_historical_problems(historical_problems, max_items=2, max_content_length=400, max_solution_length=600)}

要求：先给结论；证明题按“定义—关键依据—推导—结论”写出简洁且严谨的证明；只使用与当前问题相关的信息；总长度控制在 800 个中文字符以内。"""

    direct_math_prompt = f"""请完整而简洁地回答数学问题：{question}

如果这是一个定理或概念，请依次给出：
1. 准确的定义或定理陈述；
2. 所需条件；
3. 结论及关键公式；
4. 简短证明思路或一个典型应用。

请直接给出数学内容，不要提及知识库、系统或无法回答。"""
    primary_prompt = compact_prompt if matched_concepts else direct_math_prompt
    primary_timeout = 25.0 if matched_concepts else 70.0
    primary_max_tokens = 900 if matched_concepts else 1600

    # ========================================================
    # 7. 最终 DeepSeek 调用
    # ========================================================

    answer_source = "deepseek"
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
                    "content": primary_prompt
                }
            ],
            max_retries=1,
            max_tokens=primary_max_tokens,
            timeout=primary_timeout,
        )
        print("[Timing] final answer: %.2fs" % (time.perf_counter() - started_at))

    except Exception as exc:

        print(
            "[AI] final answer generation failed:",
            repr(exc)
        )

        # 第一轮使用图谱上下文；若模型返回空内容或超时，改用更长时限的
        # 纯数学回答请求，避免无关的知识库兜底替代真正答案。
        try:
            answer = call_deepseek(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一名严谨的中文数学教师。直接回答问题；"
                            "若问题是定理，给出定理陈述、条件和证明思路或完整证明。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"请认真回答以下数学问题，不要提及知识库或系统状态：\n\n{question}"
                        ),
                    },
                ],
                max_retries=1,
                max_tokens=1600,
                timeout=70.0,
            )
            answer_source = "deepseek_extended"
            print("[Timing] extended answer: %.2fs" % (time.perf_counter() - started_at))
        except Exception as retry_exc:
            print("[AI] extended answer generation failed:", repr(retry_exc))
            raise HTTPException(
                status_code=503,
                detail="DeepSeek 在较长回答时间内仍未返回结果，请稍后重试。",
            )

    # ========================================================
    # 8. 返回完整结果
    # ========================================================

    print("[Timing] total ask: %.2fs" % (time.perf_counter() - started_at))
    return {
        "question": question,

        "answer": answer,
        "answer_source": answer_source,

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
                ),
                "score": problem.get("score", 0.0),
                "coverage": problem.get("coverage", 0.0)
            }
            for problem in historical_problems
        ],

        "similar_problems": similar_problems,

        "knowledge_graph": {
            "nodes": graph_nodes,
            "relations": graph_relations
        }
    }
