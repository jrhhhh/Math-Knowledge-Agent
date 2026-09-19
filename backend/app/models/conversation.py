from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    title = Column(String(160), nullable=False, default="新的数学对话")
    topic = Column(String(160), nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="completed")
    answer_id = Column(Integer, nullable=True, index=True)
    request_id = Column(String(64), nullable=True, index=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class MessageConcept(Base):
    __tablename__ = "message_concepts"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    relevance = Column(Integer, nullable=False, default=100)
