from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base


class ConceptLearningProgress(Base):
    """Durable local learning state for one concept and learner profile."""

    __tablename__ = "concept_learning_progress"
    __table_args__ = (UniqueConstraint("profile_id", "concept_id", name="uq_learning_profile_concept"),)

    id = Column(Integer, primary_key=True)
    profile_id = Column(String(80), nullable=False, default="local", index=True)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="learning")
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    completed_at = Column(DateTime, nullable=True)
