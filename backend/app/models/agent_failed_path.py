from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class AgentFailedPath(Base):
    __tablename__ = "agent_failed_paths"
    id = Column(Integer, primary_key=True)
    request_id = Column(String(64), nullable=False, index=True)
    action = Column(String(80), nullable=False)
    reason = Column(Text, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
