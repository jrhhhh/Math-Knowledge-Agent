from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class AITaskStatus(Base):
    __tablename__ = "ai_task_statuses"

    id = Column(Integer, primary_key=True)
    request_id = Column(String, nullable=False, unique=True, index=True)
    question = Column(Text, nullable=False)
    status = Column(String, nullable=False, index=True)
    stage = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
