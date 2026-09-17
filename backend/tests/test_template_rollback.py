import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.templates import TemplateRequest, TemplateUpdate, create_template, update_template, rollback_template, template_events
from app.database import Base


class TemplateRollbackTests(unittest.TestCase):
    def test_update_can_be_rolled_back(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        create_template(TemplateRequest(template_id="rollback", pattern="旧问题", answer="旧答案"), db)
        update_template("rollback", TemplateUpdate(pattern="新问题", answer="新答案"), db)
        event_id = template_events("rollback", db)["events"][0]["id"]
        restored = rollback_template("rollback", event_id, db)
        self.assertEqual(restored["pattern"], "旧问题")
        self.assertEqual(restored["answer"], "旧答案")
        db.close()


if __name__ == "__main__":
    unittest.main()
