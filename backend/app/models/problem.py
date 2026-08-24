from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime

from app.database import Base


class Problem(Base):

    __tablename__ = "problems"


    id = Column(
        Integer,
        primary_key=True
    )


    title = Column(
        String,
        nullable=False
    )


    content = Column(
        Text,
        nullable=False
    )


    solution = Column(
        Text
    )


    difficulty = Column(
        String
    )


    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )