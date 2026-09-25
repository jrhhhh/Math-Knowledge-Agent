import unittest

from app.ai.agent_controller import ALLOWED_ACTIONS, extract_arithmetic_expression, plan_next_action


class AgentControllerTests(unittest.TestCase):
    def test_proof_like_task_starts_with_bounded_check(self):
        plan = plan_next_action("证明连续函数在紧集上有界")
        self.assertEqual(plan["action"], "counterexample_search")
        self.assertIn(plan["action"], ALLOWED_ACTIONS)

    def test_counterexample_plan_is_bounded(self):
        plan = plan_next_action("判断这个等式是否对任意 x 恒等", evidence=[{"status": "source_available"}])
        self.assertEqual(plan["action"], "counterexample_search")
        self.assertEqual(plan["parameters"]["range"], [-10, 10])

    def test_planner_stops_after_budget(self):
        plan = plan_next_action("证明某命题", iterations=8)
        self.assertEqual(plan["action"], "stop_inconclusive")

    def test_extracts_expression_from_chinese_question(self):
        plan = plan_next_action("请计算 6 × 7，并给出可核验过程。")
        self.assertEqual(plan["parameters"]["expression"], "6 * 7")

    def test_extracts_latest_expression_from_conversation_prompt(self):
        prompt = "最近对话：计算 2+3。\n【用户最新问题】请计算（12－2）÷5。"
        self.assertEqual(extract_arithmetic_expression(prompt), "(12-2)/5")


if __name__ == "__main__":
    unittest.main()
