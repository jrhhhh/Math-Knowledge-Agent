from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.database import Base

class AnswerReviewEvent(Base):
    __tablename__ = "answer_review_events"
    id = Column(Integer, primary_key=True)
    answer_id = Column(Integer, nullable=False, index=True)
    review_id = Column(Integer, nullable=True, index=True)
    action = Column(String(30), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
