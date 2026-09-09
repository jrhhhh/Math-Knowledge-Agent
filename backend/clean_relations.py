from app.database import SessionLocal

# ============================================================
# 必须显式导入所有 SQLAlchemy Model
# ============================================================
#
# 这些 import 的目的不是直接使用它们，
# 而是让 SQLAlchemy 在执行 query 之前
# 注册所有 ORM 类。
#

from app.models.concept import Concept
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept
from app.models.concept_relation import ConceptRelation
# 关系优先级
#
# prerequisite > supports > related
#
# 同一个 source → target
# 最终只允许存在一个关系。
RELATION_PRIORITY = {
    "prerequisite": 3,
    "supports": 2,
    "related": 1
}


def normalize_relation(relation):
    if not relation:
        return None

    relation = (
        relation
        .strip()
        .lower()
    )

    mapping = {
        "prerequisite": "prerequisite",
        "prerequisites": "prerequisite",

        "supports": "supports",
        "support": "supports",

        "related": "related"
    }

    return mapping.get(
        relation
    )


def main():

    db = SessionLocal()

    try:

        relations = (
            db.query(
                ConceptRelation
            )
            .order_by(
                ConceptRelation.id
            )
            .all()
        )

        print(
            f"当前共有 {len(relations)} 条关系"
        )

        # ====================================================
        # 第一阶段
        # 删除：
        #
        # source == target
        # ====================================================

        deleted_self = 0

        for relation in relations:

            if (
                relation.source_concept_id
                == relation.target_concept_id
            ):

                print(
                    f"删除自环关系："
                    f"{relation.id}"
                )

                db.delete(
                    relation
                )

                deleted_self += 1

        db.commit()

        # ====================================================
        # 第二阶段
        # 删除非法关系
        # ====================================================

        relations = (
            db.query(
                ConceptRelation
            )
            .all()
        )

        deleted_invalid = 0

        for relation in relations:

            normalized = normalize_relation(
                relation.relation
            )

            if normalized is None:

                print(
                    f"删除非法关系："
                    f"{relation.id} "
                    f"{relation.relation}"
                )

                db.delete(
                    relation
                )

                deleted_invalid += 1

            else:

                relation.relation = (
                    normalized
                )

        db.commit()

        # ====================================================
        # 第三阶段
        # 合并完全重复关系
        # ====================================================

        relations = (
            db.query(
                ConceptRelation
            )
            .all()
        )

        groups = {}

        for relation in relations:

            key = (
                relation.source_concept_id,
                relation.target_concept_id
            )

            groups.setdefault(
                key,
                []
            ).append(
                relation
            )

        deleted_duplicates = 0
        deleted_conflicts = 0

        for key, group in groups.items():

            if len(group) <= 1:
                continue

            # ------------------------------------------------
            # 找出优先级最高的关系
            # ------------------------------------------------

            group.sort(
                key=lambda relation:
                (
                    RELATION_PRIORITY.get(
                        relation.relation,
                        0
                    ),
                    relation.weight or 0,
                    -relation.id
                ),
                reverse=True
            )

            best = group[0]

            # ------------------------------------------------
            # 删除其他关系
            # ------------------------------------------------

            for duplicate in group[1:]:

                if (
                    duplicate.relation
                    == best.relation
                ):

                    print(
                        f"删除重复关系："
                        f"{duplicate.id} "
                        f"{duplicate.relation}"
                    )

                    deleted_duplicates += 1

                else:

                    print(
                        f"删除冲突关系："
                        f"{duplicate.id} "
                        f"{duplicate.relation}"
                        f" -> 保留 "
                        f"{best.relation}"
                    )

                    deleted_conflicts += 1

                db.delete(
                    duplicate
                )

            # ------------------------------------------------
            # 合并权重
            # ------------------------------------------------

            weights = [
                relation.weight or 0
                for relation in group
            ]

            if weights:
                best.weight = max(
                    weights
                )

        db.commit()

        # ====================================================
        # 第四阶段
        # 检查孤立引用
        # ====================================================

        relations = (
            db.query(
                ConceptRelation
            )
            .all()
        )

        concept_ids = {
            concept.id
            for concept in db.query(
                Concept
            ).all()
        }

        orphan_relations = 0

        for relation in relations:

            if (
                relation.source_concept_id
                not in concept_ids
                or
                relation.target_concept_id
                not in concept_ids
            ):

                print(
                    f"删除孤立关系："
                    f"{relation.id}"
                )

                db.delete(
                    relation
                )

                orphan_relations += 1

        db.commit()

        # ====================================================
        # 最终统计
        # ====================================================

        final_relations = (
            db.query(
                ConceptRelation
            )
            .all()
        )

        print()
        print("=" * 60)
        print("知识图谱关系清理完成")
        print("=" * 60)

        print(
            f"删除自环：{deleted_self}"
        )

        print(
            f"删除非法关系：{deleted_invalid}"
        )

        print(
            f"删除重复关系：{deleted_duplicates}"
        )

        print(
            f"删除冲突关系：{deleted_conflicts}"
        )

        print(
            f"删除孤立关系：{orphan_relations}"
        )

        print(
            f"最终关系数量："
            f"{len(final_relations)}"
        )

        print("=" * 60)

    finally:

        db.close()


if __name__ == "__main__":
    main()