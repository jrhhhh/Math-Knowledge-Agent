from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class AgentVerificationReport(Base):
    __tablename__ = "agent_verification_reports"
    id = Column(Integer, primary_key=True)
    request_id = Column(String(64), nullable=False, index=True)
    evidence_type = Column(String(40), nullable=False)
    status = Column(String(40), nullable=False)
    subject = Column(Text, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
