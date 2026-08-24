from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.database import Base


class ProblemConcept(Base):

    __tablename__ = "problem_concepts"


    id = Column(
        Integer,
        primary_key=True
    )


    problem_id = Column(
        Integer,
        ForeignKey("problems.id"),
        nullable=False
    )


    concept_id = Column(
        Integer,
        ForeignKey("concepts.id"),
        nullable=False
    )


    relation = Column(
        String,
        default="related"
    )


    importance = Column(
        Float,
        default=1.0
    )


    problem = relationship(
        "Problem",
        back_populates="concepts"
    )


    concept = relationship(
        "Concept",
        back_populates="problems"
    )