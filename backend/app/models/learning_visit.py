from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base

class LearningVisit(Base):
    __tablename__ = 'learning_visits'
    id = Column(Integer, primary_key=True)
    local_day = Column(String(10), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
