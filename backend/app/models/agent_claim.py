from sqlalchemy import Column, Integer, String, Text

from app.database import Base


class AgentClaim(Base):
    __tablename__ = "agent_claims"

    id = Column(Integer, primary_key=True)
    request_id = Column(String(64), nullable=False, index=True)
    statement = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="unverified")
    source = Column(Text, nullable=False)
    depends_on = Column(Text, nullable=False, default="[]")
    invalidation_reason = Column(Text, nullable=True)
