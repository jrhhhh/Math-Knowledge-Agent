"""Generated practice drafts stay distinct from textbook exercises and proofs."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class ConceptExerciseDraft(Base):
    __tablename__ = 'concept_exercise_drafts'

    id = Column(Integer, primary_key=True)
    concept_id = Column(Integer, ForeignKey('concepts.id'), nullable=False, index=True)
    title = Column(String(240), nullable=False)
    content = Column(Text, nullable=False)
    solution = Column(Text, nullable=False)
    difficulty = Column(String(24), nullable=False)
    objective = Column(Text, nullable=False, default='')
    context_json = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='draft')
    problem_id = Column(Integer, ForeignKey('problems.id'), nullable=True, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
