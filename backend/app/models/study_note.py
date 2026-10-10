from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from app.database import Base

class StudyNote(Base):
    __tablename__ = 'study_notes'
    id=Column(Integer,primary_key=True)
    title=Column(String(240),nullable=False)
    course=Column(String(160),nullable=False,default='未分课程')
    content=Column(Text,nullable=False)
    answer_id=Column(Integer,nullable=True,index=True)
    origin_json=Column(Text,nullable=False,default='{}')
    favorite=Column(Boolean,nullable=False,default=False)
    archived=Column(Boolean,nullable=False,default=False)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
    updated_at=Column(DateTime,nullable=False,default=datetime.utcnow)
