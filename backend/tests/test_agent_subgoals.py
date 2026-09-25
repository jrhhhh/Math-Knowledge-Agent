import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.agent_subgoal import AgentSubgoal


class AgentSubgoalTests(unittest.TestCase):
    def test_subgoal_persists_dependencies_and_status(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        try:
            item = AgentSubgoal(request_id="task-1", title="核对连续性条件", status="pending", depends_on="[2]", source="planner")
            db.add(item)
            db.commit()
            stored = db.query(AgentSubgoal).one()
            self.assertEqual(stored.status, "pending")
            self.assertEqual(stored.depends_on, "[2]")
            self.assertEqual(stored.source, "planner")
        finally:
            db.close()
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
