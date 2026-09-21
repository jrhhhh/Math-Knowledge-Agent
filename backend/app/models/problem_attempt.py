from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class ProblemAttempt(Base):
    """学生对练习的作答记录；未审核前不把作答当作掌握证据。"""

    __tablename__ = "problem_attempts"

    id = Column(Integer, primary_key=True)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False, index=True)
    answer = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="submitted", index=True)
    correctness = Column(String, nullable=False, default="unverified")
    error_type = Column(String, nullable=True)
    feedback = Column(Text, nullable=True)
    hint_level = Column(Integer, nullable=False, default=0)
    independent = Column(String, nullable=False, default="unknown")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
