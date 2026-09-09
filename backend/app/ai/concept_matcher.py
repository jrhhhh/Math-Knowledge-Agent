import math
import json
import re

from sqlalchemy.orm import Session

from app.models.concept import Concept
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept
from app.models.concept_relation import ConceptRelation

from app.ai.analyzer import client


# ============================================================
# Relation system
# ============================================================

VALID_RELATIONS = {
    "prerequisite",
    "supports",
    "defines",
    "property_of",
    "uses",
    "equivalent_to",
    "generalizes",
    "specializes",
}


# 关系优先级。
#
# 当同一 source -> target 出现多个不同关系时，
# 优先保留语义更明确的关系。
#
RELATION_PRIORITY = {
    "equivalent_to": 8,
    "defines": 7,
    "property_of": 6,
    "generalizes": 5,
    "specializes": 5,
    "prerequisite": 4,
    "uses": 3,
    "supports": 2,
}


# 兼容旧数据库中的 relation。
#
# 以前的 "related" 没有明确语义，
# 统一降级为 supports。
#
RELATION_ALIASES = {
    "related": "supports",
    "related_to": "supports",
    "dependency": "prerequisite",
    "depends_on": "prerequisite",
    "used_by": "uses",
    "property": "property_of",
}


# ============================================================
# Basic helpers
# ============================================================

def _normalize_text(text: str) -> str:
    """
    用于比较题目是否可能是同一道题。

    主要处理：
    - 大小写
    - 空白
    - 中文标点 / 英文标点
    - LaTeX 周围的空格
    """

    if not text:
        return ""

    text = str(text).strip().lower()

    # 删除所有空白
    text = re.sub(r"\s+", "", text)

    # 统一常见标点
    replacements = {
        "，": ",",
        "。": ".",
        "；": ";",
        "：": ":",
        "？": "?",
        "！": "!",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        value = float(value)

        if math.isnan(value) or math.isinf(value):
            return default

        return value

    except (TypeError, ValueError):
        return default


def _clamp(value, minimum=0.0, maximum=1.0):
    return max(
        minimum,
        min(maximum, value)
    )


# ============================================================
# Concept similarity
# ============================================================

def find_similar_concepts(
    db: Session,
    name: str,
    threshold: float = 0.80,
):
    """
    根据知识点名称寻找数据库中已有的相似知识点。

    这里主要作为基础检索。
    更复杂的语义判断交给 DeepSeek。
    """

    concepts = (
        db.query(Concept)
        .all()
    )

    if not concepts:
        return []

    normalized_name = _normalize_text(name)

    results = []

    for concept in concepts:

        concept_name = _normalize_text(
            concept.name
        )

        if not concept_name:
            continue

        # 完全相同
        if normalized_name == concept_name:
            similarity = 1.0

        # 包含关系
        elif (
            normalized_name in concept_name
            or concept_name in normalized_name
        ):
            similarity = 0.90

        else:
            similarity = 0.0

        if similarity >= threshold:

            results.append({
                "concept": concept,
                "similarity": similarity,
            })

    results.sort(
        key=lambda item: item["similarity"],
        reverse=True
    )

    return results


# ============================================================
# Semantic concept matching
# ============================================================

def semantic_match(
    concept_name: str,
    existing_concepts,
):
    """
    使用 DeepSeek 判断新知识点与已有知识点的语义相似度。

    返回：

    {
        "match": true,
        "concept_id": 1,
        "similarity": 0.95,
        "reason": "..."
    }
    """

    if not existing_concepts:
        return {
            "match": False,
            "concept_id": None,
            "similarity": 0.0,
            "reason": "数据库中没有候选知识点。",
        }

    candidates = []

    for concept in existing_concepts:

        candidates.append({
            "id": concept.id,
            "name": concept.name,
            "type": concept.type,
            "description": concept.description,
            "field": concept.field,
        })

    prompt = f"""
你是数学知识图谱中的知识点归一化助手。

现在有一个新知识点：

{concept_name}

数据库中已有以下知识点：

{json.dumps(
    candidates,
    ensure_ascii=False,
    indent=2
)}

请判断新知识点是否与已有知识点中的某一个表示同一个数学概念。

注意：

1. 同义词可以认为是同一个知识点。
2. 不同但相关的概念不能强行合并。
3. 定理、定义、方法、概念如果语义不同，不应该合并。
4. 例如：
   "紧致性" 和 "紧性" 可以合并。
5. 例如：
   "连续映射保持紧性" 和 "连续映射" 不能合并。
6. 只有高度确定是同一个知识点时才 match=true。

只返回 JSON：

{{
    "match": true,
    "concept_id": 11,
    "similarity": 0.96,
    "reason": "..."
}}

或者：

{{
    "match": false,
    "concept_id": null,
    "similarity": 0.0,
    "reason": "..."
}}
"""

    try:

        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {
                    "role": "system",
                    "content": "你是严谨的数学知识图谱归一化助手。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={
                "type": "json_object"
            }
        )

        content = (
            response
            .choices[0]
            .message
            .content
        )

        result = json.loads(content)

        return {
            "match": bool(
                result.get("match", False)
            ),
            "concept_id": result.get(
                "concept_id"
            ),
            "similarity": _safe_float(
                result.get("similarity"),
                0.0
            ),
            "reason": result.get(
                "reason",
                ""
            ),
        }

    except Exception as exc:

        print(
            "[Concept] semantic match failed:",
            repr(exc)
        )

        return {
            "match": False,
            "concept_id": None,
            "similarity": 0.0,
            "reason": "语义匹配失败。",
        }


# ============================================================
# Resolve concept
# ============================================================

def resolve_concept(
    db: Session,
    concept_name: str,
    similarity_threshold: float = 0.90,
):
    """
    将一个知识点名称解析为数据库中的唯一 Concept。

    顺序：

    1. 精确匹配
    2. 简单字符串相似
    3. DeepSeek 语义匹配
    4. 找不到则返回 None
    """

    concept_name = (
        concept_name or ""
    ).strip()

    if not concept_name:
        return None

    normalized_name = _normalize_text(
        concept_name
    )

    # --------------------------------------------------------
    # 1. 精确匹配
    # --------------------------------------------------------

    concepts = (
        db.query(Concept)
        .all()
    )

    for concept in concepts:

        if (
            _normalize_text(
                concept.name
            )
            == normalized_name
        ):
            return concept

    # --------------------------------------------------------
    # 2. 字符串相似
    # --------------------------------------------------------

    similar = find_similar_concepts(
        db,
        concept_name,
        threshold=similarity_threshold
    )

    if similar:

        best = similar[0]

        if (
            best["similarity"]
            >= similarity_threshold
        ):
            return best["concept"]

    # --------------------------------------------------------
    # 3. DeepSeek 语义匹配
    # --------------------------------------------------------

    semantic_result = semantic_match(
        concept_name,
        concepts
    )

    if (
        semantic_result["match"]
        and semantic_result["similarity"]
        >= similarity_threshold
    ):

        concept_id = semantic_result[
            "concept_id"
        ]

        concept = (
            db.query(Concept)
            .filter(
                Concept.id == concept_id
            )
            .first()
        )

        if concept is not None:
            return concept

    return None


# ============================================================
# Semantic retrieve concepts
# ============================================================

def semantic_retrieve_concepts(
    db: Session,
    query: str,
    limit: int = 10,
):
    """
    根据用户问题检索最相关的知识点。

    返回结构：

    [
        {
            "concept": Concept对象,
            "similarity": 0.95,
            "reason": "..."
        }
    ]

    注意：
    ai.py 当前依赖这个结构。
    """

    concepts = (
        db.query(Concept)
        .all()
    )

    if not concepts:
        return []

    candidate_data = []

    for concept in concepts:

        candidate_data.append({
            "id": concept.id,
            "name": concept.name,
            "type": concept.type,
            "description": concept.description,
            "field": concept.field,
            "level": concept.level,
        })

    prompt = f"""
你是数学知识图谱检索器。

用户问题：

{query}

数据库中的数学知识点：

{json.dumps(
    candidate_data,
    ensure_ascii=False,
    indent=2
)}

请从已有知识点中选择与用户问题最相关的知识点。

要求：

1. 最多选择 {limit} 个。
2. 必须使用数据库中已有知识点。
3. 不要创造新的知识点。
4. 如果知识点只是泛相关而不是核心知识，不要选择。
5. theorem、property、method 都可以选择。
6. similarity 范围为 0 到 1。
7. 按相关程度从高到低排序。
8. reason 简短说明为什么相关。

只返回 JSON：

{{
    "matches": [
        {{
            "concept_id": 5,
            "similarity": 0.98,
            "reason": "..."
        }}
    ]
}}
"""

    try:

        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是严谨的数学知识检索助手。"
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={
                "type": "json_object"
            }
        )

        content = (
            response
            .choices[0]
            .message
            .content
        )

        result = json.loads(content)

        matches = result.get(
            "matches",
            []
        )

    except Exception as exc:

        print(
            "[Concept] semantic retrieval failed:",
            repr(exc)
        )

        return []

    concept_map = {
        concept.id: concept
        for concept in concepts
    }

    results = []

    seen_ids = set()

    for match in matches:

        concept_id = match.get(
            "concept_id"
        )

        if concept_id in seen_ids:
            continue

        concept = concept_map.get(
            concept_id
        )

        if concept is None:
            continue

        similarity = _clamp(
            _safe_float(
                match.get("similarity"),
                0.0
            )
        )

        # 太低的相关度不进入知识图谱
        if similarity < 0.50:
            continue

        results.append({
            "concept": concept,
            "similarity": similarity,
            "reason": match.get(
                "reason",
                ""
            )
        })

        seen_ids.add(
            concept_id
        )

    # --------------------------------------------------------
    # 最终按 similarity 排序
    # --------------------------------------------------------

    results.sort(
        key=lambda item: item["similarity"],
        reverse=True
    )

    return results[:limit]


# ============================================================
# Historical problem retrieval
# ============================================================

def retrieve_historical_problems(
    db: Session,
    concept_ids: list[int],
    limit: int = 10,
):
    """
    根据知识点召回历史题目。

    一个题目可能对应多个知识点。

    本函数会自动：

    1. 去重
    2. 汇总知识点重要程度
    3. 计算知识点覆盖度
    4. 排序
    """

    if not concept_ids:
        return []

    concept_ids = list(
        dict.fromkeys(
            concept_ids
        )
    )

    rows = (
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
        .all()
    )

    problem_map = {}

    for problem, relation in rows:

        if problem.id not in problem_map:

            problem_map[
                problem.id
            ] = {
                "problem": problem,
                "relations": []
            }

        problem_map[
            problem.id
        ]["relations"].append(
            relation
        )

    results = []

    total_concepts = len(
        concept_ids
    )

    for problem_id, data in problem_map.items():

        problem = data["problem"]
        relations = data["relations"]

        matched_concept_ids = set()

        importance_values = []

        for relation in relations:

            matched_concept_ids.add(
                relation.concept_id
            )

            importance_values.append(
                _safe_float(
                    relation.importance,
                    0.0
                )
            )

        matched_count = len(
            matched_concept_ids
        )

        # ----------------------------------------------------
        # 知识点覆盖率
        # ----------------------------------------------------

        coverage = (
            matched_count
            / total_concepts
            if total_concepts > 0
            else 0
        )

        # ----------------------------------------------------
        # 最高 importance
        # ----------------------------------------------------

        max_importance = (
            max(importance_values)
            if importance_values
            else 0.0
        )

        # ----------------------------------------------------
        # 平均 importance
        # ----------------------------------------------------

        avg_importance = (
            sum(importance_values)
            / len(importance_values)
            if importance_values
            else 0.0
        )

        # ----------------------------------------------------
        # 最终召回分数
        #
        # coverage       45%
        # max importance 35%
        # average        20%
        # ----------------------------------------------------

        score = (
            coverage * 0.45
            + max_importance * 0.35
            + avg_importance * 0.20
        )

        matched_concepts = []

        for relation in relations:

            concept = (
                db.query(Concept)
                .filter(
                    Concept.id
                    == relation.concept_id
                )
                .first()
            )

            if concept is None:
                continue

            matched_concepts.append({
                "concept_id": concept.id,
                "concept_name": concept.name,
                "importance": _safe_float(
                    relation.importance,
                    0.0
                )
            })

        results.append({
            "id": problem.id,
            "title": problem.title,
            "content": problem.content,
            "solution": problem.solution,
            "difficulty": problem.difficulty,
            "importance": max_importance,
            "score": round(score, 4),
            "coverage": round(
                coverage,
                4
            ),
            "matched_concepts": (
                matched_concepts
            )
        })

    # --------------------------------------------------------
    # 最终排序
    # --------------------------------------------------------

    results.sort(
        key=lambda item: (
            item["score"],
            item["importance"],
            item["coverage"]
        ),
        reverse=True
    )

    return results[:limit]


# ============================================================
# Problem semantic similarity
# ============================================================

def rank_similar_problems(
    question: str,
    problems,
    result_limit: int = 5,
):
    """
    使用 DeepSeek 对候选历史题进行语义排序。

    输入的问题只与候选历史题比较。

    最终返回：

    {
        "id": ...,
        "similarity": ...,
        "reason": ...
    }
    """

    if not problems:
        return []

    candidates = []

    for problem in problems:

        candidates.append({
            "id": problem["id"],
            "title": problem["title"],
            "content": problem["content"],
            "solution": problem.get(
                "solution"
            ),
            "difficulty": problem.get(
                "difficulty"
            ),
        })

    prompt = f"""
你是数学题目相似度分析器。

当前用户问题：

{question}

候选历史题目：

{json.dumps(
    candidates,
    ensure_ascii=False,
    indent=2
)}

请判断每道历史题与当前问题的数学相似程度。

注意：

1. 比较数学结构，而不是只比较文字。
2. 相同定理、相同证明方法、相同核心知识点属于高相似。
3. 只是领域相同但数学结构明显不同，不要给高分。
4. similarity 范围 0 到 1。
5. 只返回真正有参考价值的题目。
6. 最多返回 {result_limit} 道。
7. 按 similarity 从高到低排序。

只返回 JSON：

{{
    "matches": [
        {{
            "problem_id": 1,
            "similarity": 0.96,
            "reason": "..."
        }}
    ]
}}
"""

    try:

        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是严谨的数学题目相似度分析助手。"
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={
                "type": "json_object"
            }
        )

        content = (
            response
            .choices[0]
            .message
            .content
        )

        result = json.loads(content)

        matches = result.get(
            "matches",
            []
        )

    except Exception as exc:

        print(
            "[Problem] semantic ranking failed:",
            repr(exc)
        )

        return []

    problem_map = {
        problem["id"]: problem
        for problem in problems
    }

    results = []
    seen_ids = set()

    for match in matches:

        problem_id = match.get(
            "problem_id"
        )

        if problem_id in seen_ids:
            continue

        problem = problem_map.get(
            problem_id
        )

        if problem is None:
            continue

        similarity = _clamp(
            _safe_float(
                match.get(
                    "similarity"
                ),
                0.0
            )
        )

        # 太低的相似题没有价值
        if similarity < 0.45:
            continue

        results.append({
            "id": problem["id"],
            "title": problem["title"],
            "content": problem["content"],
            "solution": problem.get(
                "solution"
            ),
            "difficulty": problem.get(
                "difficulty"
            ),
            "score": problem.get(
                "score",
                0.0
            ),
            "similarity": similarity,
            "reason": match.get(
                "reason",
                ""
            )
        })

        seen_ids.add(
            problem_id
        )

    results.sort(
        key=lambda item: (
            item["similarity"],
            item.get(
                "score",
                0.0
            )
        ),
        reverse=True
    )

    return results[:result_limit]


# ============================================================
# Search similar problems
# ============================================================

def search_similar_problems(
    db: Session,
    question: str,
    concept_ids: list[int],
    candidate_limit: int = 10,
    result_limit: int = 5,
):
    """
    历史相似题完整检索流程。

    流程：

    用户问题
        ↓
    知识点召回
        ↓
    候选历史题
        ↓
    数据库去重
        ↓
    知识点相关度排序
        ↓
    DeepSeek 语义排序
        ↓
    最终 Top-K
    """

    if not concept_ids:
        return []

    # --------------------------------------------------------
    # 1. 知识点召回历史题
    # --------------------------------------------------------

    candidates = retrieve_historical_problems(
        db=db,
        concept_ids=concept_ids,
        limit=candidate_limit
    )

    if not candidates:
        return []

    # --------------------------------------------------------
    # 2. 再次按题目内容去重
    #
    # 防止数据库中未来出现：
    #
    # id=1
    # id=99
    #
    # 但两道题实际上完全一样。
    # --------------------------------------------------------

    unique_candidates = []

    seen_signatures = set()

    for problem in candidates:

        title = _normalize_text(
            problem.get("title")
        )

        content = _normalize_text(
            problem.get("content")
        )

        signature = (
            title,
            content
        )

        if signature in seen_signatures:
            continue

        seen_signatures.add(
            signature
        )

        unique_candidates.append(
            problem
        )

    # --------------------------------------------------------
    # 3. DeepSeek 语义排序
    # --------------------------------------------------------

    ranked = rank_similar_problems(
        question=question,
        problems=unique_candidates,
        result_limit=result_limit
    )

    # --------------------------------------------------------
    # 4. 如果语义排序失败，
    #    使用数据库召回分数作为 fallback
    # --------------------------------------------------------

    if not ranked:

        fallback = []

        for problem in unique_candidates[
            :result_limit
        ]:

            fallback.append({
                "id": problem["id"],
                "title": problem["title"],
                "content": problem["content"],
                "solution": problem.get(
                    "solution"
                ),
                "difficulty": problem.get(
                    "difficulty"
                ),
                "score": problem.get(
                    "score",
                    0.0
                ),
                "similarity": None,
                "reason": (
                    "基于相关知识点召回"
                )
            })

        return fallback

    # --------------------------------------------------------
    # 5. 最终再次 ID 去重
    # --------------------------------------------------------

    final_results = []
    seen_ids = set()

    for problem in ranked:

        if problem["id"] in seen_ids:
            continue

        seen_ids.add(
            problem["id"]
        )

        final_results.append(
            problem
        )

    return final_results[
        :result_limit
    ]


# ============================================================
# Relation normalization
# ============================================================

def normalize_relation(
    relation: str
):
    """
    将 AI 返回的关系统一为标准 relation。
    """

    if not relation:
        return None

    relation = (
        str(relation)
        .strip()
        .lower()
    )

    relation = RELATION_ALIASES.get(
        relation,
        relation
    )

    if relation not in VALID_RELATIONS:
        return None

    return relation


# ============================================================
# Relation validation
# ============================================================

def validate_relation(
    source: Concept,
    target: Concept,
    relation: str,
):
    """
    使用 DeepSeek 判断关系是否合法。

    新关系体系：

    prerequisite:
        source 是 target 的学习前置知识。

    supports:
        source 对 target 的理解、证明或应用提供支持。

    defines:
        source 定义 target。

    property_of:
        source 是 target 的一个性质。

    uses:
        source 在定义、证明或构造中使用 target。

    equivalent_to:
        source 与 target 数学上等价。

    generalizes:
        source 比 target 更一般。

    specializes:
        source 是 target 的特殊情形。
    """

    relation = normalize_relation(
        relation
    )

    if relation is None:
        return {
            "valid": False,
            "confidence": 0.0,
            "reason": "非法关系类型。",
        }

    prompt = f"""
你是数学知识图谱关系验证器。

判断下面关系是否严格成立。

Source：
{source.name}

Source 类型：
{source.type}

Source 描述：
{source.description}

Target：
{target.name}

Target 类型：
{target.type}

Target 描述：
{target.description}

关系：
{relation}

关系定义：

prerequisite：
source 是学习或理解 target 时需要先掌握的知识。

supports：
source 为 target 提供证明、理解或应用上的支持，
但不表示严格的定义关系。

defines：
source 定义 target。

property_of：
source 是 target 的性质。

uses：
source 的定义、证明、构造或应用使用了 target。

equivalent_to：
source 与 target 数学上等价。

generalizes：
source 是比 target 更一般的数学对象、命题或理论。

specializes：
source 是 target 的特殊情形。

特别注意：

1. 关系方向必须正确。
2. 不能因为两个知识点都与同一个定理有关就建立 prerequisite。
3. "定理使用知识点" 应优先考虑：
   theorem --uses--> concept
4. "某性质属于某对象" 应使用：
   property --property_of--> object
5. 不确定时应该返回 false。

只返回 JSON：

{{
    "valid": true,
    "confidence": 0.95,
    "reason": "..."
}}
"""

    try:

        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是严谨的数学知识图谱关系验证器。"
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={
                "type": "json_object"
            }
        )

        content = (
            response
            .choices[0]
            .message
            .content
        )

        result = json.loads(
            content
        )

        confidence = _clamp(
            _safe_float(
                result.get(
                    "confidence"
                ),
                0.0
            )
        )

        return {
            "valid": bool(
                result.get(
                    "valid",
                    False
                )
            ),
            "confidence": confidence,
            "reason": result.get(
                "reason",
                ""
            ),
        }

    except Exception as exc:

        print(
            "[Relation] validation failed:",
            repr(exc)
        )

        return {
            "valid": False,
            "confidence": 0.0,
            "reason": "关系验证失败。",
        }


# ============================================================
# Relation existence
# ============================================================

def relation_exists(
    db: Session,
    source_concept_id: int,
    target_concept_id: int,
    relation: str = None,
):
    """
    检查关系是否已经存在。
    """

    query = (
        db.query(ConceptRelation)
        .filter(
            ConceptRelation.source_concept_id
            == source_concept_id,

            ConceptRelation.target_concept_id
            == target_concept_id,
        )
    )

    if relation is not None:

        relation = normalize_relation(
            relation
        )

        query = query.filter(
            ConceptRelation.relation
            == relation
        )

    return query.first()


# ============================================================
# Create relation
# ============================================================

def create_relation_if_valid(
    db: Session,
    source: Concept,
    target: Concept,
    relation: str,
    weight: float = 1.0,
    min_confidence: float = 0.80,
):
    """
    创建经过 AI 验证的知识图谱关系。

    规则：

    1. 禁止自环。
    2. relation 必须合法。
    3. AI confidence >= 0.80。
    4. 同一关系重复出现时更新 weight。
    5. 同一 source -> target 出现冲突关系时，
       保留优先级更高的关系。
    """

    if source is None or target is None:
        return None

    # --------------------------------------------------------
    # 禁止：
    #
    # A -> A
    # --------------------------------------------------------

    if source.id == target.id:

        print(
            "[Relation] rejected self-loop:",
            source.name
        )

        return None

    relation = normalize_relation(
        relation
    )

    if relation is None:

        print(
            "[Relation] rejected invalid relation:",
            relation
        )

        return None

    # --------------------------------------------------------
    # AI 验证
    # --------------------------------------------------------

    validation = validate_relation(
        source,
        target,
        relation
    )

    if not validation["valid"]:

        print(
            "[Relation] rejected:",
            source.name,
            relation,
            target.name,
            validation["reason"]
        )

        return None

    confidence = validation[
        "confidence"
    ]

    if confidence < min_confidence:

        print(
            "[Relation] rejected low confidence:",
            source.name,
            relation,
            target.name,
            confidence
        )

        return None

    weight = _clamp(
        _safe_float(
            weight,
            confidence
        )
    )

    # --------------------------------------------------------
    # 查询同一 source -> target 的全部关系
    # --------------------------------------------------------

    existing_relations = (
        db.query(ConceptRelation)
        .filter(
            ConceptRelation.source_concept_id
            == source.id,

            ConceptRelation.target_concept_id
            == target.id,
        )
        .all()
    )

    # --------------------------------------------------------
    # 已经存在相同关系
    # --------------------------------------------------------

    for existing in existing_relations:

        existing_relation = normalize_relation(
            existing.relation
        )

        if existing_relation == relation:

            existing.weight = max(
                _safe_float(
                    existing.weight,
                    0.0
                ),
                weight
            )

            db.commit()

            return existing

    # --------------------------------------------------------
    # 检查冲突关系
    # --------------------------------------------------------

    new_priority = RELATION_PRIORITY.get(
        relation,
        0
    )

    for existing in existing_relations:

        existing_relation = normalize_relation(
            existing.relation
        )

        existing_priority = (
            RELATION_PRIORITY.get(
                existing_relation,
                0
            )
        )

        # 新关系优先级更高：
        # 删除旧关系。
        if new_priority > existing_priority:

            db.delete(
                existing
            )

        # 旧关系优先级更高：
        # 不创建新关系。
        elif new_priority < existing_priority:

            db.commit()

            return existing

        # 优先级相同：
        # 保留旧关系，避免产生歧义。
        else:

            db.commit()

            return existing

    # --------------------------------------------------------
    # 创建新关系
    # --------------------------------------------------------

    new_relation = ConceptRelation(
        source_concept_id=source.id,
        target_concept_id=target.id,
        relation=relation,
        weight=weight
    )

    db.add(
        new_relation
    )

    db.commit()
    db.refresh(
        new_relation
    )

    return new_relation