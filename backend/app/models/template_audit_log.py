from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.models.concept import Base

class TemplateAuditLog(Base):
    __tablename__ = "local_template_audit_logs"
    id = Column(Integer, primary_key=True)
    action = Column(String(40), nullable=False, index=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)
