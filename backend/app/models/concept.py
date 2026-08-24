from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Concept(Base):

    __tablename__ = "concepts"


    id = Column(
        Integer,
        primary_key=True
    )


    name = Column(
        String,
        nullable=False
    )


    description = Column(
        Text
    )


    field = Column(
        String
    )


    level = Column(
        Integer,
        default=1
    )


    problems = relationship(
        "ProblemConcept",
        back_populates="concept"
    )