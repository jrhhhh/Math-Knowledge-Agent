from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AgentSubgoal(Base):
    __tablename__ = "agent_subgoals"

    id = Column(Integer, primary_key=True)
    request_id = Column(String(64), nullable=False, index=True)
    title = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="pending")
    depends_on = Column(Text, nullable=True)
    source = Column(String(120), nullable=False, default="user")
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
