from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AgentTaskEvent(Base):
    """Append-only state transitions for an AI task."""

    __tablename__ = "agent_task_events"

    id = Column(Integer, primary_key=True)
    request_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    stage = Column(String(120), nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
