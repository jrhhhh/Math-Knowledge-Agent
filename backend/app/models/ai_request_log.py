from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, Text, String

from app.database import Base


class AIRequestLog(Base):
    __tablename__ = "ai_request_logs"

    id = Column(Integer, primary_key=True)
    request_id = Column(String, nullable=False, index=True)
    question = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    duration_seconds = Column(Float, nullable=True)
    error_code = Column(String, nullable=True)
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
