import unittest

from app.ai.agent_controller import ALLOWED_ACTIONS, extract_arithmetic_expression, plan_next_action, extract_calculus_request


class AgentControllerTests(unittest.TestCase):
    def test_proof_like_task_starts_with_knowledge_retrieval(self):
        plan = plan_next_action("证明连续函数在紧集上有界")
        self.assertEqual(plan["action"], "retrieve_knowledge")
        self.assertIn(plan["action"], ALLOWED_ACTIONS)

    def test_proof_plan_advances_from_retrieval_to_draft_to_review(self):
        retrieved = {"action": "retrieve_knowledge", "result": {"status": "retrieved", "concepts": [{"name": "紧性"}], "sources": []}}
        plan = plan_next_action("证明连续函数在紧集上有界", evidence=[retrieved])
        self.assertEqual(plan["action"], "draft_proof")
        self.assertEqual(plan["parameters"]["concepts"], [{"name": "紧性"}])

        drafted = {"action": "draft_proof", "result": {"status": "draft_ready", "proof": "设 K 紧。由定理可得结论。"}}
        plan = plan_next_action("证明连续函数在紧集上有界", evidence=[retrieved, drafted])
        self.assertEqual(plan["action"], "review_revise_review")
        self.assertEqual(plan["parameters"]["proof"], drafted["result"]["proof"])

        reviewed = {"action": "review_revise_review", "result": {"status": "model_reviewed"}}
        plan = plan_next_action("证明连续函数在紧集上有界", evidence=[retrieved, drafted, reviewed])
        self.assertEqual(plan["action"], "stop_inconclusive")

    def test_missing_arithmetic_expression_requests_clarification(self):
        plan = plan_next_action("计算表达式")
        self.assertEqual(plan["action"], "request_clarification")

    def test_definite_integral_question_routes_to_exact_calculus(self):
        plan = plan_next_action("求定积分 x²，x 从 0 到 1")
        self.assertEqual(plan["action"], "exact_calculus")
        self.assertEqual(plan["parameters"], {"operation": "integrate_definite", "expression": "x**2", "lower": "0", "upper": "1"})
        self.assertEqual(extract_calculus_request("求导 x^3 + 2x"), {"operation": "differentiate", "expression": "x^3 + 2x"})

    def test_counterexample_without_expressions_requests_clarification(self):
        plan = plan_next_action("判断等式是否对任意 x 恒等")
        self.assertEqual(plan["action"], "request_clarification")

    def test_counterexample_plan_is_bounded(self):
        plan = plan_next_action(
            "判断这个等式是否对任意 x 恒等",
            evidence=[{"status": "source_available"}],
            parameters={"left": "x ** 2", "right": "x"},
        )
        self.assertEqual(plan["action"], "counterexample_search")
        self.assertEqual(plan["parameters"]["range"], [-10, 10])

    def test_planner_stops_after_budget(self):
        plan = plan_next_action("证明某命题", iterations=8)
        self.assertEqual(plan["action"], "stop_inconclusive")

    def test_calculus_proof_is_not_misrouted_to_computation(self):
        plan = plan_next_action("证明连续函数的定积分存在")
        self.assertEqual(plan["action"], "retrieve_knowledge")

    def test_integral_missing_bound_requests_clarification(self):
        plan = plan_next_action("求定积分", parameters={"operation": "integrate_definite", "expression": "x^2", "lower": 0})
        self.assertEqual(plan["action"], "request_clarification")
        self.assertEqual(plan["parameters"]["missing"], ["upper"])

    def test_natural_integral_preserves_expression_when_bounds_missing(self):
        plan = plan_next_action("求定积分 x²")
        self.assertEqual(plan["action"], "request_clarification")
        self.assertEqual(plan["parameters"]["missing"], ["lower", "upper"])
        parsed = extract_calculus_request("求定积分 x²")
        self.assertEqual(parsed["expression"], "x**2")

    def test_extracts_expression_from_chinese_question(self):
        plan = plan_next_action("请计算 6 × 7，并给出可核验过程。")
        self.assertEqual(plan["parameters"]["expression"], "6 * 7")

    def test_extracts_latest_expression_from_conversation_prompt(self):
        prompt = "最近对话：计算 2+3。\n【用户最新问题】请计算（12－2）÷5。"
        self.assertEqual(extract_arithmetic_expression(prompt), "(12-2)/5")


if __name__ == "__main__":
    unittest.main()
