from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String
from app.models.concept import Base

class QuestionSample(Base):
    __tablename__ = "anonymous_question_samples"
    id = Column(Integer, primary_key=True)
    question_hash = Column(String(64), nullable=False, index=True)
    question_length = Column(Integer, nullable=False)
    source = Column(String(30), nullable=False, default="ask")
    matched_template_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)
