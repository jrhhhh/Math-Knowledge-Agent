import unittest

from fastapi.testclient import TestClient

from app.main import app


class AgentRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_run_completes_exact_calculation_with_evidence(self):
        response = self.client.post("/ai/agent/run", json={
            "question": "计算表达式",
            "request_id": "agent-run-test-exact",
            "parameters": {"expression": "7 * 6"},
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "completed_with_evidence")
        self.assertEqual(body["evidence"][-1]["value"], 42)

    def test_run_finds_counterexample(self):
        response = self.client.post("/ai/agent/run", json={
            "question": "判断等式是否对任意 x 恒等",
            "request_id": "agent-run-test-counterexample",
            "parameters": {"left": "x ** 2", "right": "x"},
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "refuted")

    def test_run_requests_missing_parameters(self):
        response = self.client.post("/ai/agent/run", json={
            "question": "计算表达式",
            "request_id": "agent-run-test-missing",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "needs_clarification")


if __name__ == "__main__":
    unittest.main()
