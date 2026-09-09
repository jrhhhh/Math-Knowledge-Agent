from app.database import SessionLocal
from app.models.concept import Concept
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept
from app.models.concept_relation import ConceptRelation


# ============================================================
# 配置
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


# ============================================================
# 工具函数
# ============================================================

def get_concept_id(db, name: str):
    """
    根据概念名称获取 concept_id。
    找不到则返回 None。
    """
    concept = (
        db.query(Concept)
        .filter(Concept.name == name)
        .first()
    )

    if concept is None:
        print(f"⚠️ 找不到概念：{name}")
        return None

    return concept.id


def delete_all_relations(db):
    """
    删除当前所有知识图谱关系。

    这是一次性的关系体系迁移，因此直接清空旧关系，
    再按照新的语义体系重新建立。
    """
    count = db.query(ConceptRelation).count()

    if count > 0:
        db.query(ConceptRelation).delete(
            synchronize_session=False
        )

    db.commit()

    print(f"已删除旧关系：{count} 条")


def create_relation(
    db,
    source_name: str,
    target_name: str,
    relation: str,
    weight: float = 1.0,
):
    """
    创建一条知识图谱关系。
    """

    if relation not in VALID_RELATIONS:
        print(
            f"⚠️ 非法关系类型："
            f"{source_name} --[{relation}]--> {target_name}"
        )
        return False

    # 禁止自环
    if source_name == target_name:
        print(
            f"⚠️ 跳过自环："
            f"{source_name} --[{relation}]--> {target_name}"
        )
        return False

    source_id = get_concept_id(db, source_name)
    target_id = get_concept_id(db, target_name)

    if source_id is None or target_id is None:
        print(
            f"⚠️ 跳过关系："
            f"{source_name} --[{relation}]--> {target_name}"
        )
        return False

    # 防止重复
    existing = (
        db.query(ConceptRelation)
        .filter(
            ConceptRelation.source_concept_id == source_id,
            ConceptRelation.target_concept_id == target_id,
            ConceptRelation.relation == relation,
        )
        .first()
    )

    if existing:
        return False

    relation_obj = ConceptRelation(
        source_concept_id=source_id,
        target_concept_id=target_id,
        relation=relation,
        weight=weight,
    )

    db.add(relation_obj)

    return True


# ============================================================
# 主迁移
# ============================================================

def migrate():
    db = SessionLocal()

    try:
        print("=" * 60)
        print("开始迁移知识图谱关系")
        print("=" * 60)

        # ----------------------------------------------------
        # 第一步：删除旧关系
        # ----------------------------------------------------

        delete_all_relations(db)

        # ----------------------------------------------------
        # 第二步：建立新的、经过审核的关系体系
        # ----------------------------------------------------

        relations = [

            # =================================================
            # 1. 拓扑空间基础结构
            # =================================================

            (
                "拓扑空间",
                "开集",
                "prerequisite",
                1.0,
            ),

            (
                "拓扑空间",
                "连续映射",
                "prerequisite",
                1.0,
            ),

            (
                "拓扑空间",
                "紧性",
                "prerequisite",
                1.0,
            ),

            (
                "拓扑空间",
                "紧集",
                "prerequisite",
                1.0,
            ),

            # =================================================
            # 2. 开覆盖 → 有限子覆盖 → 紧性
            # =================================================

            (
                "开集",
                "开覆盖",
                "prerequisite",
                1.0,
            ),

            (
                "开覆盖",
                "有限子覆盖",
                "prerequisite",
                1.0,
            ),

            (
                "有限子覆盖",
                "紧性",
                "prerequisite",
                1.0,
            ),

            # =================================================
            # 3. 连续映射与原像性质
            # =================================================

            (
                "原像保持开集",
                "连续映射",
                "property_of",
                1.0,
            ),

            # =================================================
            # 4. 连续映射保持紧性定理
            # =================================================

            (
                "紧集",
                "连续映射保持紧性",
                "prerequisite",
                1.0,
            ),

            (
                "连续映射保持紧性",
                "连续映射",
                "uses",
                1.0,
            ),

            (
                "连续映射保持紧性",
                "紧集",
                "uses",
                1.0,
            ),

            (
                "连续映射保持紧性",
                "紧性",
                "uses",
                1.0,
            ),

            (
                "连续映射保持紧性",
                "原像保持开集",
                "uses",
                1.0,
            ),

            (
                "连续映射保持紧性",
                "有限子覆盖",
                "uses",
                1.0,
            ),

            # =================================================
            # 5. 开覆盖转化法与定理
            # =================================================

            (
                "原像保持开集",
                "开覆盖转化法",
                "supports",
                1.0,
            ),

            (
                "开覆盖转化法",
                "连续映射保持紧性",
                "supports",
                1.0,
            ),

            # =================================================
            # 6. 原像作为证明工具
            # =================================================

            (
                "原像",
                "开覆盖转化法",
                "supports",
                1.0,
            ),
        ]

        created = 0

        for (
            source_name,
            target_name,
            relation,
            weight,
        ) in relations:

            success = create_relation(
                db=db,
                source_name=source_name,
                target_name=target_name,
                relation=relation,
                weight=weight,
            )

            if success:
                created += 1

        db.commit()

        # ----------------------------------------------------
        # 第三步：输出最终关系
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("知识图谱关系迁移完成")
        print("=" * 60)

        final_relations = (
            db.query(ConceptRelation)
            .order_by(
                ConceptRelation.source_concept_id,
                ConceptRelation.target_concept_id,
            )
            .all()
        )

        for rel in final_relations:

            source = db.query(Concept).filter(
                Concept.id == rel.source_concept_id
            ).first()

            target = db.query(Concept).filter(
                Concept.id == rel.target_concept_id
            ).first()

            if source is None or target is None:
                continue

            print(
                f"{source.name} "
                f"--[{rel.relation}]--> "
                f"{target.name}"
            )

        print()
        print(f"本次新建关系：{created}")
        print(f"最终关系数量：{len(final_relations)}")
        print("=" * 60)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":
    migrate()