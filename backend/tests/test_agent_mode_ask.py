import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class AgentModeAskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_agent_mode_passes_exact_tool_evidence_to_answer(self):
        result = {
            "answer": "计算结果为 42。",
            "answer_source": "test",
            "answer_quality": {"score": 1, "correctness_status": "unverified", "checks": {}, "formula": {"valid": True, "issues": []}},
            "knowledge_sources": [], "concepts": [], "historical_problems": [], "similar_problems": [],
            "knowledge_graph": {"nodes": [], "relations": []}, "formula_fixes": [],
        }
        with patch("app.api.ai.call_deepseek", return_value=result["answer"]):
            response = self.client.post("/ai/ask", json={"question": "计算这个数", "agent_mode": True, "agent_parameters": {"expression": "6 * 7"}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agent_tool_evidence"][0]["value"], 42)

    def test_agent_mode_extracts_exact_expression_from_question(self):
        with patch("app.api.ai.call_deepseek", return_value="计算结果为 42。"):
            response = self.client.post(
                "/ai/ask",
                json={"question": "请计算 6 × 7，并给出可核验过程。", "agent_mode": True},
            )
        self.assertEqual(response.status_code, 200)
        evidence = response.json()["agent_tool_evidence"][0]
        self.assertEqual(evidence["status"], "computed")
        self.assertEqual(evidence["expression"], "6 * 7")
        self.assertEqual(evidence["value"], 42)
        persisted = self.client.get(f"/ai/answers/{response.json()['answer_id']}/evidence")
        self.assertEqual(persisted.status_code, 200)
        self.assertTrue(any(item["status"] == "computed" for item in persisted.json()["items"]))

    def test_agent_mode_can_attach_lean_evidence(self):
        result = {
            "answer": "已给出说明。",
            "answer_source": "test",
            "answer_quality": {"score": 1, "correctness_status": "unverified", "checks": {}, "formula": {"valid": True, "issues": []}},
            "knowledge_sources": [], "concepts": [], "historical_problems": [], "similar_problems": [],
            "knowledge_graph": {"nodes": [], "relations": []}, "formula_fixes": [],
        }
        lean_result = {"status": "formally_verified", "theorem": "nat_add_zero", "evidence_type": "formal_verification", "method": "lean_fixed_template"}
        with patch("app.api.ai.call_deepseek", return_value=result["answer"]), patch("app.api.ai.check_known_theorem", return_value=lean_result):
            response = self.client.post("/ai/ask", json={"question": "使用 Lean 形式化检查", "agent_mode": True, "agent_parameters": {"theorem": "nat_add_zero"}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agent_tool_evidence"][0]["status"], "formally_verified")


if __name__ == "__main__":
    unittest.main()
