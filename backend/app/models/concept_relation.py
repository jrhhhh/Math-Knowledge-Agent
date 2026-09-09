from sqlalchemy import Column, Integer, String, ForeignKey, Float
from app.database import Base


class ConceptRelation(Base):
    __tablename__ = "concept_relations"

    id = Column(Integer, primary_key=True)

    source_concept_id = Column(
        Integer,
        ForeignKey("concepts.id"),
        nullable=False
    )

    target_concept_id = Column(
        Integer,
        ForeignKey("concepts.id"),
        nullable=False
    )

    # 数学知识之间的关系
    #
    # prerequisite : 前置知识
    # supports     : 支撑/辅助理解
    # defines      : 定义
    # property_of  : 某个对象的性质
    # uses         : 使用某个知识
    # equivalent_to : 等价
    # generalizes  : 推广
    # specializes  : 特化/特殊情形
    relation = Column(
        String,
        nullable=False,
        default="related"
    )

    # AI 判断关系的可信度
    weight = Column(
        Float,
        default=1.0
    )