import unittest

from fastapi.testclient import TestClient

from app.main import app


class AgentSubgoalApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_subgoal_lifecycle(self):
        created = self.client.post("/ai/tasks/subgoal-api-test/subgoals", json={"title": "检查条件", "source": "planner"})
        self.assertEqual(created.status_code, 201)
        item_id = created.json()["id"]
        updated = self.client.patch(f"/ai/tasks/subgoal-api-test/subgoals/{item_id}", json={"status": "completed"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["status"], "completed")
        listed = self.client.get("/ai/tasks/subgoal-api-test/subgoals")
        self.assertEqual(listed.json()["items"][0]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
