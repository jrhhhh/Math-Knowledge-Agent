import json

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.models.concept import Concept
from app.ai.analyzer import client


# ============================================================
# 1. 模糊匹配
# ============================================================

def find_similar_concepts(
    db: Session,
    name: str,
    threshold: int = 60
):
    """
    根据名称相似度寻找候选知识点。
    """

    concepts = db.query(Concept).all()

    candidates = []

    for concept in concepts:

        score = fuzz.ratio(
            name,
            concept.name
        )

        if score >= threshold:

            candidates.append({
                "concept": concept,
                "score": score
            })

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return candidates


# ============================================================
# 2. DeepSeek 语义判断
# ============================================================

def semantic_match(
    name1: str,
    name2: str
):
    """
    判断两个知识点名称是否表示同一个数学知识点。
    """

    prompt = f"""
你是一名专业的数学知识图谱专家。

请判断下面两个名称是否表示同一个数学知识点。

知识点 A：
{name1}

知识点 B：
{name2}

请特别注意：

1. 同义词可以认为是同一个知识点。
2. 表达方式不同但数学含义完全相同，可以认为是同一个知识点。
3. “紧性”和“紧集”通常不是简单的同义词，要根据数学含义谨慎判断。
4. “连续映射”和“连续函数”在具体数学语境下可能相同，但需要判断语境。
5. 概念、定理、性质、方法不能因为相关就认为是同一个知识点。
6. 上位概念和下位概念不能认为是同一个知识点。
7. 不要因为两个知识点经常一起出现就认为相同。

只返回 JSON：

{{
    "same": true,
    "confidence": 0.95,
    "reason": "两个名称表示相同的数学概念"
}}

或者：

{{
    "same": false,
    "confidence": 0.95,
    "reason": "两个名称虽然相关，但数学含义不同"
}}
"""

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一名专业、严谨的数学知识图谱专家。"
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

    return json.loads(
        response.choices[0].message.content
    )


# ============================================================
# 3. 解析知识点
# ============================================================

def resolve_concept(
    db: Session,
    name: str,
    threshold: int = 60,
    semantic_threshold: float = 0.85
):
    """
    将 AI 提取出的知识点名称解析为数据库中的已有知识点。

    优先级：

    1. 完全相同
    2. 名称高度相似
    3. DeepSeek 语义判断

    如果没有找到相同知识点，则返回 None。
    """

    name = name.strip()

    if not name:
        return None

    # --------------------------------------------------------
    # 第一层：完全匹配
    # --------------------------------------------------------

    concept = db.query(
        Concept
    ).filter(
        Concept.name == name
    ).first()

    if concept is not None:
        return concept

    # --------------------------------------------------------
    # 第二层：模糊匹配
    # --------------------------------------------------------

    candidates = find_similar_concepts(
        db,
        name,
        threshold
    )

    # --------------------------------------------------------
    # 第三层：DeepSeek 语义判断
    # --------------------------------------------------------

    for candidate in candidates[:3]:

        candidate_concept = candidate["concept"]

        match_result = semantic_match(
            name,
            candidate_concept.name
        )

        same = match_result.get(
            "same",
            False
        )

        confidence = match_result.get(
            "confidence",
            0
        )

        if (
            same is True
            and
            confidence >= semantic_threshold
        ):
            return candidate_concept

    return None


# ============================================================
# 4. 语义检索用户问题
# ============================================================

def semantic_retrieve_concepts(
    db: Session,
    question: str
):
    """
    使用 DeepSeek 从已有知识点中进行语义检索。

    注意：
    这里只允许返回数据库中已经存在的知识点。
    不会创建新知识点。
    """

    concepts = db.query(
        Concept
    ).all()

    if not concepts:
        return []

    concept_list = "\n".join(
        f"{concept.id}. "
        f"{concept.name} "
        f"({concept.type})"
        for concept in concepts
    )

    prompt = f"""
你是一名专业的数学知识图谱检索专家。

现在需要从已有的数学知识点中，
找出与用户问题最相关的知识点。

用户问题：

{question}

已有知识点：

{concept_list}

要求：

1. 只能从已有知识点中选择。
2. 不要创造新的知识点。
3. 可以选择：
   - concept
   - theorem
   - property
   - method
4. 优先选择能够直接帮助回答问题的知识点。
5. 如果一个定理可以直接回答用户的问题，
   优先选择该定理。
6. 最多选择 5 个。
7. 按相关程度从高到低排列。
8. 如果只是弱相关，不要选择。
9. 不要因为两个知识点名字相似就同时选择。
10. 尽量避免选择重复含义的知识点。

只返回 JSON：

{{
    "concept_ids": [5, 15, 2],
    "reason": "简短说明"
}}
"""

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一名严谨的数学知识图谱检索专家。"
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

    result = json.loads(
        response.choices[0].message.content
    )

    concept_ids = result.get(
        "concept_ids",
        []
    )

    if not isinstance(
        concept_ids,
        list
    ):
        return []

    matched = []

    for concept_id in concept_ids[:5]:

        if not isinstance(
            concept_id,
            int
        ):
            continue

        concept = db.query(
            Concept
        ).filter(
            Concept.id == concept_id
        ).first()

        if concept is not None:
            matched.append(concept)

    return matched


# ============================================================
# 5. 校验知识图谱关系
# ============================================================

def validate_relation(
    source_name: str,
    target_name: str,
    relation_type: str
):
    """
    DeepSeek 检查知识图谱关系是否正确。

    prerequisite：
        source → target
        source 是理解 target 的前置知识。

    supports：
        source → target
        source 直接支持 target 的证明、推导或建立。

    related：
        两者存在明确数学关联，
        但没有明确的前置或支撑关系。
    """

    prompt = f"""
你是一名专业的数学知识图谱专家。

请判断下面这条数学知识关系是否正确。

source：
{source_name}

target：
{target_name}

relation：
{relation_type}

关系定义：

1. prerequisite：

source → target

表示 source 是理解 target
所需要的前置知识。

2. supports：

source → target

表示 source 可以直接支持
target 的证明、推导或建立。

3. related：

表示两个知识点存在明确的数学关联，
但没有明确的 prerequisite 或 supports 关系。

请检查：

1. 关系方向是否正确。
2. 关系类型是否正确。
3. 数学上是否真实成立。
4. 不要因为两个知识点经常同时出现，
   就认为它们存在关系。
5. 不要把上位概念和下位概念
   自动判断成 prerequisite。
6. 不要把定义中的词语
   自动判断成 prerequisite。

只返回 JSON：

{{
    "valid": true,
    "confidence": 0.95,
    "reason": "简短说明"
}}
"""

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是专业的数学知识图谱关系校验专家。"
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

    return json.loads(
        response.choices[0].message.content
    )