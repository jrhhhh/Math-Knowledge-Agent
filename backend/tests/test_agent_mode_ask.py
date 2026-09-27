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

    def test_agent_mode_attaches_exact_calculus_evidence(self):
        with patch("app.api.ai.call_deepseek", side_effect=TimeoutError("模型不可用")) as model:
            response = self.client.post("/ai/ask", json={"question": "求定积分 x²，x 从 0 到 1", "agent_mode": True})
        model.assert_not_called()
        self.assertEqual(response.status_code, 200)
        evidence = response.json()["agent_tool_evidence"][0]
        self.assertEqual(evidence["evidence_type"], "exact_definite_integral")
        self.assertEqual(evidence["value"], "1/3")
        self.assertEqual(response.json()["answer_source"], "exact_calculus_tool")
        self.assertIn("定积分为 1/3", response.json()["answer"])

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

    def test_agent_mode_identity_disproof_needs_no_model(self):
        with patch("app.api.ai.call_deepseek", side_effect=TimeoutError("模型不可用")) as model:
            response = self.client.post("/ai/ask", json={"question": "验证多项式恒等式 x*(x-1) = 0", "agent_mode": True})
        model.assert_not_called()
        self.assertEqual(response.status_code, 200)
        evidence = response.json()["agent_tool_evidence"][0]
        self.assertFalse(evidence["identity"])
        self.assertEqual(evidence["status"], "identity_disproved")
        self.assertEqual(evidence["difference"], "x**2 - x")
        self.assertIn("结论：不是恒等式", response.json()["answer"])
        self.assertEqual(response.json()["answer_source"], "polynomial_identity_tool")
        self.assertIsNone(response.json()["model_answer_before_tool_guard"])

    def test_identity_does_not_stream_unchecked_model_tokens(self):
        from app.api.ai import _ask_impl, AskRequest
        from app.database import SessionLocal

        chunks = []
        with SessionLocal() as db, patch("app.api.ai.call_deepseek", return_value="恒等式成立。") as model:
            result = _ask_impl(AskRequest(question="验证多项式恒等式 x*(x-1) = 0", agent_mode=True), db, stream_callback=chunks.append)
        self.assertIn("不是恒等式", result["answer"])
        self.assertFalse(chunks)
        model.assert_not_called()

    def test_conversation_plans_current_question_not_history(self):
        conversation = self.client.post("/conversations", json={"title": "工具上下文隔离测试"}).json()
        with patch("app.api.ai.call_deepseek", side_effect=TimeoutError("不应调用模型")) as model:
            response = self.client.post(f"/conversations/{conversation['id']}/messages", json={"content": "验证多项式恒等式 (x+1)^2 = x²+2x+1", "agent_mode": True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["result"]["agent_tool_evidence"][0]["identity"])
        model.assert_not_called()

    def test_calculus_boundaries_do_not_generate_unchecked_answers(self):
        for question, expected in (("求定积分 x²", "积分下限、积分上限"), ("求导 sin(x)", "工具范围不足")):
            with self.subTest(question=question), patch("app.api.ai.call_deepseek", side_effect=TimeoutError("不应调用模型")) as model:
                response = self.client.post("/ai/ask", json={"question": question, "agent_mode": True})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["answer_source"], "tool_boundary")
                self.assertIn(expected, response.json()["answer"])
                model.assert_not_called()
                reports = self.client.get(f"/ai/tasks/{response.json()['request_id']}/verification-reports")
                self.assertEqual(reports.status_code, 200)
                self.assertEqual(reports.json()["items"], [])


if __name__ == "__main__":
    unittest.main()
