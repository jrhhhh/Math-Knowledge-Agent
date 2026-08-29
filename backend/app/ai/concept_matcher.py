import json

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.models.concept import Concept
from app.ai.analyzer import client


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


def semantic_match(
    name1: str,
    name2: str
):
    """
    使用 DeepSeek 判断两个数学知识点
    是否属于同一个数学概念。
    """

    prompt = f"""
你是一名专业的数学知识图谱专家。

请判断下面两个数学知识点是否表示同一个数学概念。

知识点A：
{name1}

知识点B：
{name2}

请考虑数学语义，而不仅仅是文字是否相似。

判断规则：

1. 如果两个名称在数学语义上表示同一个概念，返回 true。
2. 如果只是相关，但不是同一个概念，返回 false。
3. 定理、性质、方法和普通概念不要随意合并。
4. 连续函数和连续映射在很多数学语境下可以表示相同或高度重合的概念。
5. 紧集和紧致性通常不是完全相同的概念。

只返回 JSON：

{{
    "same": true,
    "confidence": 0.95,
    "reason": "简短说明"
}}

same 必须是 true 或 false。

confidence 必须是 0 到 1 之间的小数。

reason 必须简短。
"""

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {
                "role": "system",
                "content": "你是专业的数学知识图谱专家。"
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