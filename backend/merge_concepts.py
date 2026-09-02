from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.concept import Concept
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept
from app.models.concept_relation import ConceptRelation


# ============================================================
# 合并两个知识点
# ============================================================

def merge_concepts(
    db: Session,
    old_id: int,
    new_id: int
):
    """
    将 old_id 合并到 new_id。

    使用 SQL 直接迁移外键，避免 SQLAlchemy ORM
    在删除旧 Concept 时把外键自动设置为 NULL。
    """

    old = db.query(
        Concept
    ).filter(
        Concept.id == old_id
    ).first()

    new = db.query(
        Concept
    ).filter(
        Concept.id == new_id
    ).first()

    if old is None:
        print(
            f"[SKIP] Concept {old_id} 不存在"
        )
        return

    if new is None:
        print(
            f"[ERROR] Concept {new_id} 不存在"
        )
        return

    if old.id == new.id:
        print(
            "[SKIP] old_id 和 new_id 相同"
        )
        return

    print()
    print("=" * 60)
    print(
        f"合并：[{old.id}] {old.name}"
        f"  →  [{new.id}] {new.name}"
    )
    print("=" * 60)

    # ========================================================
    # 1. 迁移 ProblemConcept
    # ========================================================

    problem_links = db.query(
        ProblemConcept
    ).filter(
        ProblemConcept.concept_id == old.id
    ).all()

    moved_problem_links = 0
    deleted_problem_links = 0

    for link in problem_links:

        existing = db.query(
            ProblemConcept
        ).filter(
            ProblemConcept.problem_id
            == link.problem_id,

            ProblemConcept.concept_id
            == new.id
        ).first()

        if existing is not None:

            # 已经存在同一道题 → 新知识点的关联
            # 保留 importance 更高的记录

            if (
                link.importance is not None
                and
                (
                    existing.importance is None
                    or
                    link.importance > existing.importance
                )
            ):
                existing.importance = link.importance

            db.delete(link)

            deleted_problem_links += 1

        else:

            # 不使用 ORM 属性修改，
            # 直接 SQL UPDATE 外键

            db.execute(
                text(
                    """
                    UPDATE problem_concepts
                    SET concept_id = :new_id
                    WHERE id = :link_id
                    """
                ),
                {
                    "new_id": new.id,
                    "link_id": link.id
                }
            )

            moved_problem_links += 1

    # ========================================================
    # 2. 迁移 ConceptRelation
    # ========================================================

    relations = db.query(
        ConceptRelation
    ).filter(
        (
            (ConceptRelation.source_concept_id == old.id)
            |
            (ConceptRelation.target_concept_id == old.id)
        )
    ).all()

    moved_relations = 0
    deleted_relations = 0
    self_relations_deleted = 0

    for relation in relations:

        source_id = relation.source_concept_id
        target_id = relation.target_concept_id

        if source_id == old.id:
            source_id = new.id

        if target_id == old.id:
            target_id = new.id

        # ----------------------------------------------------
        # 防止出现：
        #
        # new → new
        # ----------------------------------------------------

        if source_id == target_id:

            db.delete(relation)

            self_relations_deleted += 1

            continue

        # ----------------------------------------------------
        # 检查迁移后是否已经存在相同关系
        # ----------------------------------------------------

        existing = db.query(
            ConceptRelation
        ).filter(
            ConceptRelation.source_concept_id
            == source_id,

            ConceptRelation.target_concept_id
            == target_id,

            ConceptRelation.relation
            == relation.relation
        ).first()

        if existing is not None:

            # 保留权重更高的关系

            if (
                relation.weight is not None
                and
                (
                    existing.weight is None
                    or
                    relation.weight > existing.weight
                )
            ):
                existing.weight = relation.weight

            db.delete(relation)

            deleted_relations += 1

        else:

            # ------------------------------------------------
            # 直接 SQL 更新外键
            # ------------------------------------------------

            db.execute(
                text(
                    """
                    UPDATE concept_relations
                    SET
                        source_concept_id = :source_id,
                        target_concept_id = :target_id
                    WHERE id = :relation_id
                    """
                ),
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "relation_id": relation.id
                }
            )

            moved_relations += 1

    # ========================================================
    # 3. 先 flush
    # ========================================================

    db.flush()

    # ========================================================
    # 4. 删除旧 Concept
    # ========================================================

    db.execute(
        text(
            """
            DELETE FROM concepts
            WHERE id = :old_id
            """
        ),
        {
            "old_id": old.id
        }
    )

    # ========================================================
    # 5. 提交
    # ========================================================

    db.commit()

    print(
        f"ProblemConcept 移动：{moved_problem_links}"
    )

    print(
        f"ProblemConcept 重复删除：{deleted_problem_links}"
    )

    print(
        f"ConceptRelation 移动：{moved_relations}"
    )

    print(
        f"ConceptRelation 重复删除：{deleted_relations}"
    )

    print(
        f"自指关系删除：{self_relations_deleted}"
    )

    print(
        f"完成：{old.id} → {new.id}"
    )


# ============================================================
# 检查知识点
# ============================================================

def show_concepts(db: Session):

    print()
    print("=" * 60)
    print("当前知识点")
    print("=" * 60)

    concepts = db.query(
        Concept
    ).order_by(
        Concept.id
    ).all()

    for concept in concepts:

        print(
            f"{concept.id}"
            f"|{concept.name}"
            f"|{concept.type}"
        )


# ============================================================
# 检查孤立外键
# ============================================================

def check_broken_references(db: Session):

    print()
    print("=" * 60)
    print("检查数据库引用")
    print("=" * 60)

    # --------------------------------------------------------
    # ProblemConcept
    # --------------------------------------------------------

    broken_problem_links = db.execute(
        text(
            """
            SELECT
                pc.id,
                pc.problem_id,
                pc.concept_id
            FROM problem_concepts pc
            LEFT JOIN concepts c
                ON pc.concept_id = c.id
            WHERE c.id IS NULL
            """
        )
    ).fetchall()

    print(
        f"ProblemConcept 孤立引用："
        f"{len(broken_problem_links)}"
    )

    # --------------------------------------------------------
    # ConceptRelation source
    # --------------------------------------------------------

    broken_source = db.execute(
        text(
            """
            SELECT
                cr.id,
                cr.source_concept_id
            FROM concept_relations cr
            LEFT JOIN concepts c
                ON cr.source_concept_id = c.id
            WHERE c.id IS NULL
            """
        )
    ).fetchall()

    print(
        f"ConceptRelation source 孤立引用："
        f"{len(broken_source)}"
    )

    # --------------------------------------------------------
    # ConceptRelation target
    # --------------------------------------------------------

    broken_target = db.execute(
        text(
            """
            SELECT
                cr.id,
                cr.target_concept_id
            FROM concept_relations cr
            LEFT JOIN concepts c
                ON cr.target_concept_id = c.id
            WHERE c.id IS NULL
            """
        )
    ).fetchall()

    print(
        f"ConceptRelation target 孤立引用："
        f"{len(broken_target)}"
    )


# ============================================================
# 主程序
# ============================================================

def main():

    db: Session = SessionLocal()

    try:

        print()
        print("开始知识点规范化...")
        print()

        show_concepts(db)

        # ----------------------------------------------------
        # 1. 紧致性 → 紧性
        #
        # 注意：
        # 这一组合并已经执行成功。
        #
        # 所以这里不要再次执行。
        # ----------------------------------------------------

        # ----------------------------------------------------
        # 2. 连续映射的原像开集性质
        #    → 原像保持开集
        # ----------------------------------------------------

        merge_concepts(
            db,
            old_id=12,
            new_id=13
        )

        # ----------------------------------------------------
        # 最终检查
        # ----------------------------------------------------

        show_concepts(db)

        check_broken_references(db)

        print()
        print("=" * 60)
        print("知识点规范化完成")
        print("=" * 60)

    except Exception:

        db.rollback()

        print()
        print("=" * 60)
        print("规范化失败，事务已回滚")
        print("=" * 60)

        raise

    finally:

        db.close()


if __name__ == "__main__":
    main()