import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.ai import set_task_status
from app.database import Base
from app.models.agent_task_event import AgentTaskEvent
from app.models.ai_task_status import AITaskStatus


class AgentTaskEventTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()

    def test_status_updates_append_events(self):
        set_task_status("task-1", "queued", "准备问答", db=self.db, question="计算 1+1")
        set_task_status("task-1", "succeeded", "回答完成", db=self.db, question="计算 1+1")
        task = self.db.query(AITaskStatus).one()
        events = self.db.query(AgentTaskEvent).order_by(AgentTaskEvent.id).all()
        self.assertEqual(task.status, "succeeded")
        self.assertEqual(task.goal, "计算 1+1")
        self.assertEqual([item.stage for item in events], ["准备问答", "回答完成"])

        set_task_status("task-1", "succeeded", "回答完成", db=self.db, question="计算 1+1", result={"answer_quality": {"correctness_status": "unverified"}, "knowledge_sources": []})
        self.assertEqual(self.db.query(AITaskStatus).one().termination_reason, "answer_completed")


if __name__ == "__main__":
    unittest.main()
