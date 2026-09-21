from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, String

from app.database import Base


class AIRetryJob(Base):
    __tablename__ = "ai_retry_jobs"

    id = Column(String, primary_key=True)
    operation = Column(String, nullable=False)
    question = Column(Text, nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True, index=True)
    status = Column(String, nullable=False, default="queued")
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    error = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
