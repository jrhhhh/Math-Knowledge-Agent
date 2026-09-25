from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AnswerEvidence(Base):
    """Evidence attached to one answer; generation is never treated as proof."""

    __tablename__ = "answer_evidence"

    id = Column(Integer, primary_key=True)
    answer_id = Column(Integer, ForeignKey("answer_records.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="unverified")
    subject = Column(Text, nullable=False)
    method = Column(String(120), nullable=False)
    assumptions = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
