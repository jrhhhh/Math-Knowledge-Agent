import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class AgentRevisionStepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_revision_is_not_marked_verified(self):
        with patch("app.api.ai.call_deepseek", return_value="修订后的答案"):
            response = self.client.post("/ai/agent/step", json={
                "question": "证明函数有界",
                "action": "revise_answer",
                "parameters": {"answer": "函数有界。", "feedback": "补充连续性和紧致性条件。"},
            })
        self.assertEqual(response.status_code, 200)
        result = response.json()["result"]
        self.assertEqual(result["status"], "model_revised")
        self.assertEqual(result["answer"], "修订后的答案")
        self.assertIn("重新审查", result["assumptions"])


if __name__ == "__main__":
    unittest.main()
