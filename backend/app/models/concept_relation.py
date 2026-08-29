from sqlalchemy import Column, Integer, String, Float, ForeignKey

from app.database import Base


class ConceptRelation(Base):

    __tablename__ = "concept_relations"

    id = Column(
        Integer,
        primary_key=True
    )

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

    relation = Column(
        String,
        default="related"
    )

    weight = Column(
        Float,
        default=1.0
    )