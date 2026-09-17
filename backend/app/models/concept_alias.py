from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base


class ConceptAlias(Base):
    __tablename__ = "concept_aliases"
    __table_args__ = (UniqueConstraint("concept_id", "alias", name="uq_concept_alias"),)

    id = Column(Integer, primary_key=True)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=False)
    alias = Column(String, nullable=False)
