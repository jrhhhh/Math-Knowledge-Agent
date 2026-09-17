from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.models.concept import Base


class LocalTemplate(Base):
    __tablename__ = "local_answer_templates"

    id = Column(Integer, primary_key=True)
    template_id = Column(String(100), unique=True, nullable=False, index=True)
    pattern = Column(String(500), nullable=False)
    answer = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
