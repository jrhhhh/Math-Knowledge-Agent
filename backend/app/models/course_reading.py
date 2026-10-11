"""Book-bound reading state, immutable discussion scopes and exercise drafts."""
from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Text, ForeignKey, DateTime
from app.database import Base

class CourseReadingState(Base):
    __tablename__ = 'course_reading_states'
    document_id = Column(Integer, ForeignKey('knowledge_documents.id'), primary_key=True)
    page = Column(Integer, nullable=False, default=1)
    zoom = Column(Float, nullable=False, default=1)
    panel_ratio = Column(Float, nullable=False, default=.58)
    print_offset = Column(Integer, nullable=False, default=0)
    bookmarks_json = Column(Text, nullable=False, default='[]')
    conversation_id = Column(Integer, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class CourseConversation(Base):
    __tablename__ = 'course_conversations'
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('knowledge_documents.id'), nullable=False, index=True)
    title = Column(String(160), nullable=False, default='教材讨论')
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class CourseMessage(Base):
    __tablename__ = 'course_messages'
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('course_conversations.id'), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='completed')
    context_json = Column(Text, nullable=False, default='{}')
    request_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class CourseExerciseDraft(Base):
    __tablename__ = 'course_exercise_drafts'
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('knowledge_documents.id'), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey('course_messages.id'), nullable=False, unique=True)
    title = Column(String(240), nullable=False)
    content = Column(Text, nullable=False)
    solution = Column(Text, nullable=False)
    source_json = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='draft')
    problem_id = Column(Integer, nullable=True)
