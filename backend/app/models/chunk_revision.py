from datetime import datetime
from sqlalchemy import Column,Integer,Text,String,DateTime,ForeignKey
from app.database import Base
class ChunkRevision(Base):
    __tablename__='knowledge_chunk_revisions'
    id=Column(Integer,primary_key=True)
    chunk_id=Column(Integer,ForeignKey('knowledge_chunks.id'),nullable=False,index=True)
    content=Column(Text,nullable=False)
    heading=Column(String(240),nullable=True)
    review_status=Column(String(20),nullable=False)
    reason=Column(String(240),nullable=True)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
