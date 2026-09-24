import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.concepts import create_concept
from app.database import Base
from app.models.concept import Concept


class ConceptCreationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_same_name_and_field_reuses_existing_concept(self):
        first = create_concept("  紧致性冒烟测试 ", "用于测试", "拓扑学", self.db)
        second = create_concept("紧致性冒烟测试", "重复提交", "拓扑学", self.db)
        self.assertEqual(first.id, second.id)
        self.assertEqual(self.db.query(Concept).count(), 1)


if __name__ == "__main__":
    unittest.main()
