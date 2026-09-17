from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, String

from app.database import Base


class GraphCandidateEvent(Base):
    """候选图谱审核生命周期事件，用于审计和问题追踪。"""

    __tablename__ = "graph_candidate_events"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("graph_candidates.id"), nullable=False, index=True)
    action = Column(String, nullable=False)
    detail_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
