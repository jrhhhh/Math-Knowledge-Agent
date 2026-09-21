from sqlalchemy import Column, ForeignKey, Integer, String

from app.database import Base


class ProblemSource(Base):
    """Traceable textbook source for a curated exercise."""

    __tablename__ = "problem_sources"

    id = Column(Integer, primary_key=True)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(Integer, ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    relation = Column(String(30), nullable=False, default="inspired_by")
