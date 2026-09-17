from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.models.concept import Base


class LocalTemplate(Base):
    __tablename__ = "local_answer_templates"

    id = Column(Integer, primary_key=True)
    template_id = Column(String(100), unique=True, nullable=False, index=True)
    pattern = Column(String(500), nullable=False)
    answer = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
