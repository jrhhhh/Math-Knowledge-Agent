import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class AgentStepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_executes_exact_arithmetic_and_returns_trace_id(self):
        response = self.client.post("/ai/agent/step", json={
            "question": "计算一个式子",
            "action": "exact_arithmetic",
            "parameters": {"expression": "(3 + 2) ** 2"},
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result"]["value"], 25)
        self.assertTrue(body["completed"])
        self.assertTrue(body["request_id"])

    def test_rejects_missing_counterexample_parameters(self):
        response = self.client.post("/ai/agent/step", json={
            "question": "判断恒等式",
            "action": "counterexample_search",
        })
        self.assertEqual(response.status_code, 422)

    def test_executes_registered_lean_check(self):
        lean_result = {"status": "formally_verified", "theorem": "nat_add_zero", "evidence_type": "formal_verification", "method": "lean_fixed_template"}
        with patch("app.api.ai.check_known_theorem", return_value=lean_result):
            response = self.client.post("/ai/agent/step", json={
                "question": "使用 Lean 形式化检查",
                "action": "lean_check",
                "parameters": {"theorem": "nat_add_zero"},
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["status"], "formally_verified")


if __name__ == "__main__":
    unittest.main()
