from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True)
    title = Column(String(240), nullable=False)
    course = Column(String(160), nullable=False, index=True)
    chapter = Column(String(160), nullable=True, index=True)
    source_uri = Column(String(500), nullable=True)
    review_status = Column(String(20), nullable=False, default="draft", index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=True, index=True)
    page_start = Column(Integer, nullable=True)
    page_end = Column(Integer, nullable=True)
    heading = Column(String(240), nullable=True)
    chunk_type = Column(String(30), nullable=False, default="explanation")
    content = Column(Text, nullable=False)
    review_status = Column(String(20), nullable=False, default="unreviewed", index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
