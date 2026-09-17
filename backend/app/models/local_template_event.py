from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.models.concept import Base

class LocalTemplateEvent(Base):
    __tablename__ = "local_answer_template_events"
    id = Column(Integer, primary_key=True)
    template_id = Column(String(100), nullable=False, index=True)
    action = Column(String(30), nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
