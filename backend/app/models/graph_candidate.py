from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, Text, String

from app.database import Base


class GraphCandidate(Base):
    """AI 生成的候选图谱，保存原始结果以便校验和追溯。"""

    __tablename__ = "graph_candidates"

    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)
    graph_json = Column(Text, nullable=False)
    validation_json = Column(Text, nullable=False, default="{}")
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
