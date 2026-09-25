import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class AgentProofStepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_review_proof_is_explicitly_model_reviewed(self):
        raw = '{"valid": false, "summary": "缺少条件", "steps": [], "missing_assumptions": ["连续性"], "suggestions": []}'
        with patch("app.api.ai.call_deepseek", return_value=raw):
            response = self.client.post("/ai/agent/step", json={
                "question": "证明函数有界",
                "action": "review_proof",
                "parameters": {"proof": "因此函数有界。"},
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["status"], "model_reviewed")
        self.assertFalse(response.json()["result"]["review"]["valid"])


if __name__ == "__main__":
    unittest.main()
