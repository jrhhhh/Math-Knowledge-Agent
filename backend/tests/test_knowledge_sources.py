import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.knowledge import concept_sources, search_knowledge_chunks
from app.database import Base
from app.models.concept import Concept
from app.models.knowledge_source import KnowledgeChunk, KnowledgeDocument


class KnowledgeSourceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.concept = Concept(name="紧集", description="每个开覆盖有有限子覆盖", field="拓扑学")
        self.db.add(self.concept)
        self.db.commit()
        document = KnowledgeDocument(title="最优化导论", course="最优化导论", chapter="数学知识回顾", source_uri="local://textbook.pdf", review_status="approved")
        self.db.add(document)
        self.db.flush()
        self.db.add(KnowledgeChunk(document_id=document.id, concept_id=self.concept.id, page_start=8, page_end=9, heading="紧集的定义", chunk_type="definition", content="设 K 是拓扑空间中的子集。若每个开覆盖都有有限子覆盖，则称 K 为紧集。", review_status="approved"))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_search_returns_source_page_and_total(self):
        result = search_knowledge_chunks(q="有限子覆盖", course="最优化导论", offset=0, limit=10, db=self.db)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["page_start"], 8)
        self.assertEqual(result["items"][0]["review_status"], "approved")

    def test_concept_sources_are_linked_to_real_chunk(self):
        result = concept_sources(self.concept.id, self.db)
        self.assertEqual(result["items"][0]["chunk_type"], "definition")
        self.assertEqual(result["items"][0]["document_title"], "最优化导论")


if __name__ == "__main__":
    unittest.main()
