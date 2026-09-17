from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.database import Base

class AnswerReview(Base):
    __tablename__ = "answer_reviews"
    id = Column(Integer, primary_key=True)
    answer_id = Column(Integer, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
