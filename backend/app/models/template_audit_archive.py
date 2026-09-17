from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.models.concept import Base

class TemplateAuditArchive(Base):
    __tablename__ = "local_template_audit_archives"
    id = Column(Integer, primary_key=True)
    original_id = Column(Integer, nullable=False, index=True)
    action = Column(String(40), nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)
    archived_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
