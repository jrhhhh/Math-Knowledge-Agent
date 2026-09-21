from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class GraphEvidence(Base):
    """可审计的图谱节点或关系来源。"""

    __tablename__ = "graph_evidence"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("graph_candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_type = Column(String(16), nullable=False)  # node / edge
    subject_key = Column(String(240), nullable=False)
    source_kind = Column(String(24), nullable=False)  # conversation / ai_inferred
    source_message_id = Column(Integer, ForeignKey("conversation_messages.id"), nullable=True, index=True)
    excerpt = Column(Text, nullable=False, default="")
    review_status = Column(String(20), nullable=False, default="unreviewed")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
