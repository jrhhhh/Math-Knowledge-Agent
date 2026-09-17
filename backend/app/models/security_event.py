from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.database import Base

class SecurityEvent(Base):
    __tablename__ = "security_events"
    id = Column(Integer, primary_key=True)
    event = Column(String(40), nullable=False, index=True)
    ip_address = Column(String(64), nullable=True)
    path = Column(String(200), nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)
