import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class AgentReviewLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_review_revise_review_is_bounded(self):
        first = '{"valid": false, "summary": "缺少条件", "steps": [], "missing_assumptions": ["连续性"], "suggestions": ["补充条件"]}'
        second = '{"valid": true, "summary": "步骤完整", "steps": [], "missing_assumptions": [], "suggestions": []}'
        with patch("app.api.ai.call_deepseek", side_effect=[first, "补充条件后的证明", second]):
            response = self.client.post("/ai/agent/step", json={
                "question": "证明函数有界",
                "action": "review_revise_review",
                "parameters": {"proof": "因此函数有界。"},
            })
        self.assertEqual(response.status_code, 200)
        result = response.json()["result"]
        self.assertEqual(result["status"], "model_reviewed_after_revision")
        self.assertTrue(result["second_review"]["valid"])
        self.assertIn("最多执行一次", result["assumptions"])


if __name__ == "__main__":
    unittest.main()
