from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint

from app.database import Base


class ProblemHint(Base):
    """Curated, graduated hint for a problem; level 1 is the least revealing."""

    __tablename__ = "problem_hints"
    __table_args__ = (UniqueConstraint("problem_id", "level", name="uq_problem_hint_level"),)

    id = Column(Integer, primary_key=True)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True)
    level = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    review_status = Column(String(20), nullable=False, default="approved")
