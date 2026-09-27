import unittest
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.ai_task_status import AITaskStatus


class AgentRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_run_completes_exact_calculation_with_evidence(self):
        response = self.client.post("/ai/agent/run", json={
            "question": "计算表达式",
            "request_id": f"agent-run-test-exact-{uuid4().hex}",
            "parameters": {"expression": "7 * 6"},
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "completed_with_evidence")
        self.assertEqual(body["evidence"][-1]["value"], 42)

    def test_run_finds_counterexample(self):
        response = self.client.post("/ai/agent/run", json={
            "question": "判断等式是否对任意 x 恒等",
            "request_id": f"agent-run-test-counterexample-{uuid4().hex}",
            "parameters": {"left": "x ** 2", "right": "x"},
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "refuted")

    def test_run_checks_polynomial_identity_without_sampling(self):
        for question, status in (("验证多项式恒等式 (x+1)^2 = x²+2x+1", "completed_with_evidence"), ("验证多项式恒等式 x*(x-1) = 0", "refuted")):
            with self.subTest(question=question):
                response = self.client.post("/ai/agent/run", json={"question": question, "request_id": uuid4().hex})
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["status"], status)
                self.assertEqual(body["trace"][0]["action"], "polynomial_identity")
                self.assertEqual(body["evidence"][0]["method"], "exact_rational_coefficient_comparison")

    def test_step_budget_preserves_work_without_claiming_completion(self):
        with patch("app.api.ai.safe_semantic_retrieve_concepts", return_value=[]), patch("app.api.ai.retrieve_audited_sources", return_value=[]):
            response = self.client.post("/ai/agent/run", json={"question": "证明连续函数在紧集上有界", "request_id": uuid4().hex, "max_steps": 1})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "budget_exhausted")
        self.assertEqual(body["stop_reason"], "step_budget")
        self.assertEqual(len(body["trace"]), 1)
        self.assertEqual(body["budget"]["enforcement"], "between_actions")
        persisted = self.client.get(f"/ai/tasks/{body['request_id']}")
        self.assertEqual(persisted.status_code, 200)
        self.assertEqual(persisted.json()["termination_reason"], "step_budget")
        self.assertEqual(persisted.json()["result"]["status"], "budget_exhausted")
        self.assertEqual(persisted.json()["result"]["trace"], body["trace"])

    def test_run_requests_missing_parameters(self):
        response = self.client.post("/ai/agent/run", json={
            "question": "计算表达式",
            "request_id": f"agent-run-test-missing-{uuid4().hex}",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "needs_clarification")

    def test_resume_integral_preserves_task_and_step_budget(self):
        request_id = uuid4().hex
        initial = self.client.post("/ai/agent/run", json={"question": "求定积分 x²", "request_id": request_id}).json()
        self.assertEqual(initial["status"], "needs_clarification")
        response = self.client.post(f"/ai/agent/{request_id}/resume", json={"parameters": {"lower": "0", "upper": "1"}})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["request_id"], request_id)
        self.assertEqual(body["status"], "completed_with_evidence")
        self.assertEqual(body["evidence"][-1]["value"], "1/3")
        self.assertEqual(len(body["trace"]), 2)
        self.assertEqual(body["trace"][0], initial["trace"][0])
        self.assertEqual(self.client.post(f"/ai/agent/{request_id}/resume", json={"parameters": {"upper": "2"}}).status_code, 409)

    def test_resume_rejects_goal_change_and_respects_used_steps(self):
        request_id = uuid4().hex
        self.client.post("/ai/agent/run", json={"question": "求定积分 x²", "request_id": request_id, "max_steps": 1})
        self.assertEqual(self.client.post(f"/ai/agent/{request_id}/resume", json={"parameters": {"expression": "x³"}}).status_code, 422)
        body = self.client.post(f"/ai/agent/{request_id}/resume", json={"parameters": {"lower": "0", "upper": "1"}}).json()
        self.assertEqual(body["status"], "budget_exhausted")
        self.assertEqual(body["steps"], 1)

    def test_resume_accepts_partial_bounds_without_losing_previous_input(self):
        request_id = uuid4().hex
        self.client.post("/ai/agent/run", json={"question": "求定积分 x²", "request_id": request_id, "max_steps": 4})
        first = self.client.post(f"/ai/agent/{request_id}/resume", json={"parameters": {"lower": "0"}}).json()
        self.assertEqual(first["status"], "needs_clarification")
        self.assertEqual(first["trace"][-1]["result"]["missing"], ["upper"])
        final = self.client.post(f"/ai/agent/{request_id}/resume", json={"parameters": {"upper": "1"}}).json()
        self.assertEqual(final["status"], "completed_with_evidence")
        self.assertEqual(final["evidence"][-1]["value"], "1/3")
        self.assertEqual(final["steps"], 3)
        self.assertEqual(final["trace"][:2], first["trace"])

    def test_resume_rejects_exhausted_execution_time(self):
        request_id = uuid4().hex
        initial = self.client.post("/ai/agent/run", json={"question": "求定积分 x²", "request_id": request_id, "max_elapsed_seconds": 1})
        self.assertEqual(initial.status_code, 200)
        with SessionLocal() as db:
            task = db.query(AITaskStatus).filter(AITaskStatus.request_id == request_id).one()
            saved = json.loads(task.result_json)
            saved["resume_state"]["max_elapsed_seconds"] = 0
            task.result_json = json.dumps(saved)
            db.commit()
        response = self.client.post(f"/ai/agent/{request_id}/resume", json={"parameters": {"lower": "0", "upper": "1"}})
        self.assertEqual(response.status_code, 409)

    def test_resume_cannot_claim_already_running_task(self):
        request_id = uuid4().hex
        self.client.post("/ai/agent/run", json={"question": "求定积分 x²", "request_id": request_id})
        with SessionLocal() as db:
            task = db.query(AITaskStatus).filter(AITaskStatus.request_id == request_id).one()
            task.status = "running"
            db.commit()
        with patch("app.api.ai._execute_agent_run") as execute:
            response = self.client.post(f"/ai/agent/{request_id}/resume", json={"parameters": {"lower": "0", "upper": "1"}})
        self.assertEqual(response.status_code, 409)
        execute.assert_not_called()

    def test_concurrent_resume_only_executes_once(self):
        request_id = uuid4().hex
        self.client.post("/ai/agent/run", json={"question": "求定积分 x²", "request_id": request_id})
        entered, release = threading.Event(), threading.Event()

        def hold_execution(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise AssertionError("并发测试等待释放超时")
            return {"status": "test_execution_claimed"}

        with patch("app.api.ai._execute_agent_run", side_effect=hold_execution) as execute, ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.client.post, f"/ai/agent/{request_id}/resume", json={"parameters": {"lower": "0", "upper": "1"}})
            try:
                self.assertTrue(entered.wait(3))
                second = self.client.post(f"/ai/agent/{request_id}/resume", json={"parameters": {"lower": "0", "upper": "1"}})
                self.assertEqual(second.status_code, 409)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=3).status_code, 200)
            execute.assert_called_once()

    def test_failed_tool_input_is_saved_without_becoming_evidence(self):
        response = self.client.post("/ai/agent/run", json={"question": "求导 sin(x)", "request_id": uuid4().hex})
        body = response.json()
        self.assertEqual(body["status"], "failed")
        self.assertFalse(body["evidence"])
        self.assertEqual(body["failed_attempt"]["action"], "exact_calculus")
        self.assertEqual(body["failed_attempt"]["parameters"]["expression"], "sin(x)")
        persisted = self.client.get(f"/ai/tasks/{body['request_id']}").json()
        self.assertEqual(persisted["result"]["failed_attempt"], body["failed_attempt"])

    def test_repeated_action_stops_without_reexecution(self):
        plan = {"action": "retrieve_knowledge", "parameters": {"query": "连续性"}}
        with patch("app.api.ai.plan_next_action", return_value=plan), patch("app.api.ai.agent_step", return_value={"result": {"status": "retrieved"}}) as step:
            response = self.client.post("/ai/agent/run", json={"question": "证明函数连续", "request_id": uuid4().hex, "max_steps": 4})
        body = response.json()
        self.assertEqual(body["status"], "inconclusive")
        self.assertEqual(body["stop_reason"], "repeated_action")
        self.assertEqual(body["steps"], 1)
        step.assert_called_once()

    def test_elapsed_budget_stops_before_next_action(self):
        clock = [0.0]

        def completed_retrieval(*args, **kwargs):
            clock[0] = 2.0
            return {"result": {"status": "retrieved", "concepts": [], "sources": []}}

        with patch("app.api.ai.time.monotonic", side_effect=lambda: clock[0]), patch("app.api.ai.agent_step", side_effect=completed_retrieval) as step:
            response = self.client.post("/ai/agent/run", json={"question": "证明连续函数在紧集上有界", "request_id": uuid4().hex, "max_elapsed_seconds": 1})
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "budget_exhausted")
        self.assertEqual(body["stop_reason"], "elapsed_time_budget")
        self.assertEqual(body["steps"], 1)
        self.assertEqual(body["budget"]["elapsed_seconds"], 2.0)
        step.assert_called_once()

    def test_rejects_invalid_time_budgets(self):
        for budget in (0, -1, 601):
            with self.subTest(budget=budget):
                response = self.client.post("/ai/agent/run", json={"question": "求导 x²", "max_elapsed_seconds": budget})
                self.assertEqual(response.status_code, 422)

    def test_calculus_operation_alias_survives_run_parameter_merge(self):
        for operation in ("derivative", "求导"):
            with self.subTest(operation=operation):
                response = self.client.post("/ai/agent/run", json={"question": "求导函数", "request_id": uuid4().hex, "parameters": {"operation": operation, "expression": "x^3"}})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "completed_with_evidence")
                self.assertEqual(response.json()["trace"][0]["result"]["derivative"], "3*x**2")

    def test_run_computes_high_calculus_integral_exactly(self):
        response = self.client.post("/ai/agent/run", json={
            "question": "求定积分 x²，x 从 0 到 1",
            "request_id": f"agent-run-test-integral-{uuid4().hex}",
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "completed_with_evidence")
        self.assertEqual(body["trace"][0]["action"], "exact_calculus")
        self.assertEqual(body["trace"][0]["result"]["value"], "1/3")
        step = body["trace"][0]
        self.assertEqual(step["parameters"]["expression"], "x**2")
        self.assertEqual(step["parameters"]["lower"], "0")
        self.assertEqual(step["parameters"]["upper"], "1")
        self.assertGreaterEqual(step["duration_seconds"], 0)
        replay = self.client.post("/ai/tools/exact-calculus", json=step["parameters"])
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json(), step["result"])
        self.assertEqual(body["trace"][0]["result"]["antiderivative"], "1/3*x**3")

    def test_run_reuses_single_step_executor_for_proof_flow(self):
        from app.models.concept import Concept

        concept = Concept(id=1, name="紧性", type="definition")
        retrieval = [{"concept": concept, "similarity": 0.9}]
        with patch("app.api.ai.safe_semantic_retrieve_concepts", return_value=retrieval), \
             patch("app.api.ai.retrieve_audited_sources", return_value=[]), \
             patch("app.api.ai.call_deepseek", return_value="设 K 紧，由连续函数在紧集上有界定理可得结论。"), \
             patch("app.api.ai.analyze_proof", return_value={"review_source": "local_rule_fallback", "valid": False}):
            response = self.client.post("/ai/agent/run", json={
                "question": "证明连续函数在紧集上有界",
                "request_id": f"agent-run-test-proof-flow-{uuid4().hex}",
                "max_steps": 4,
            })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([step["action"] for step in body["trace"]], [
            "retrieve_knowledge", "draft_proof", "review_revise_review",
        ])
        self.assertEqual(body["status"], "inconclusive")
        self.assertEqual(body["trace"][1]["result"]["artifact_type"], "model_generated_draft")

    def test_high_calculus_regression_matrix_without_model_calls(self):
        cases = [
            ("求导 x¹²", "completed_with_evidence", "derivative", "12*x**11"),
            ("求定积分 x，x 从 1/2 到 0", "completed_with_evidence", "value", "-1/8"),
            ("求定积分 x³，x 从 -1 到 1", "completed_with_evidence", "value", "0"),
            ("求导 sin(x)", "failed", None, None),
            ("求导 1/x", "failed", None, None),
            ("求定积分 x²", "needs_clarification", None, None),
        ]
        with patch("app.api.ai.call_deepseek") as model:
            for question, status, key, expected in cases:
                with self.subTest(question=question):
                    response = self.client.post("/ai/agent/run", json={"question": question, "request_id": f"calculus-matrix-{uuid4().hex}"})
                    self.assertEqual(response.status_code, 200)
                    body = response.json()
                    self.assertEqual(body["status"], status)
                    if key:
                        self.assertEqual(body["trace"][0]["result"][key], expected)
                    if status == "failed":
                        self.assertFalse(body["evidence"])
            model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
