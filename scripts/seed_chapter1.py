#!/usr/bin/env python3
"""Seed a small curated Chapter 1 learning set from the reviewed PDF pages."""

from app.database import Base, SessionLocal, engine
from app.models.concept import Concept
from app.models.knowledge_source import KnowledgeChunk
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept
from app.models.problem_source import ProblemSource
from app.models.problem_hint import ProblemHint


CONCEPTS = {
    "直接证明法": ("从已知前提逐步推导结论的证明方法。", "证明方法", "method"),
    "逆反命题": ("利用 A 蕴含 B 与非 B 蕴含非 A 等价性进行证明的命题形式。", "证明方法", "concept"),
    "反证法": ("从命题成立与结论不成立出发，推出矛盾的证明方法。", "证明方法", "method"),
    "数学归纳法": ("验证初始项，并证明 n 项成立蕴含 n+1 项成立的证明方法。", "证明方法", "method"),
}

PROBLEMS = [
    ("判断规则的逆反命题", "说明命题 A⇒B 的逆反命题是什么，并解释为什么二者等价。", "写出逻辑等价式：A⇒B 等价于 ¬B⇒¬A。", "基础", "逆反命题", ["先写出原命题的前件和后件。", "同时交换位置并分别取否定，得到 ¬B⇒¬A。"]),
    ("选择合适的证明方法", "要证明：若 n 是正整数，则 1+2+…+n=n(n+1)/2。应选择哪种证明方法？写出关键的两个证明条件。", "使用数学归纳法：验证 n=1；假设 n=k 成立，再证明 n=k+1 成立。", "基础", "数学归纳法", ["注意命题由正整数 n 参数化。", "分别写出归纳起点和从 k 到 k+1 的归纳步骤。"]),
    ("反证法的起点", "若要用反证法证明命题 A⇒B，证明开始时应同时假设哪些命题？", "假设 A 成立且 B 不成立，即 A 且 ¬B，然后推出矛盾。", "基础", "反证法", ["反证法不是直接重复结论。", "保留原条件 A，再假设结论 B 不成立。"]),
    ("直接法的证明结构", "用直接法证明 A⇒B 时，证明过程中的起点和终点分别是什么？", "从 A 开始，经过合法推导得到 B。", "基础", "直接证明法", ["先明确已知条件 A。", "每一步使用定义、定理或已知性质，最后得到 B。"]),
]


def get_or_create_concept(db, name, description, field, concept_type):
    item = db.query(Concept).filter(Concept.name == name, Concept.field == field).first()
    if item is None:
        item = Concept(name=name, description=description, field=field, type=concept_type, level=1)
        db.add(item)
        db.flush()
    return item


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.page_start == 16, KnowledgeChunk.review_status == "approved").all()
        if not chunks:
            raise SystemExit("未找到已审核的第 16 页教材片段，请先导入 PDF 页面")
        source_chunk = chunks[0]
        concepts = {name: get_or_create_concept(db, name, description, field, kind) for name, (description, field, kind) in CONCEPTS.items()}
        created = 0
        for title, content, solution, difficulty, concept_name, hints in PROBLEMS:
            problem = db.query(Problem).filter(Problem.title == title).first()
            if problem is None:
                problem = Problem(title=title, content=content, solution=solution, difficulty=difficulty)
                db.add(problem)
                db.flush()
                created += 1
            concept = concepts[concept_name]
            if not db.query(ProblemConcept).filter_by(problem_id=problem.id, concept_id=concept.id).first():
                db.add(ProblemConcept(problem_id=problem.id, concept_id=concept.id, relation="tests", importance=1.0))
            if not db.query(ProblemSource).filter_by(problem_id=problem.id, chunk_id=source_chunk.id).first():
                db.add(ProblemSource(problem_id=problem.id, chunk_id=source_chunk.id, relation="inspired_by"))
            for level, hint in enumerate(hints, 1):
                if not db.query(ProblemHint).filter_by(problem_id=problem.id, level=level).first():
                    db.add(ProblemHint(problem_id=problem.id, level=level, content=hint, review_status="approved"))
        db.commit()
        print({"created_problems": created, "source_chunk_id": source_chunk.id, "concepts": list(concepts)})


if __name__ == "__main__":
    main()
