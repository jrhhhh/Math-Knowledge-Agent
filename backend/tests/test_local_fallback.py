import unittest

from app.ai.local_fallback import local_math_answer, match_local_template


class LocalFallbackTests(unittest.TestCase):
    def test_known_theorem_answers_are_actionable(self):
        answer = local_math_answer("柯西中值定理")
        self.assertIn("罗尔定理", answer)
        self.assertIn("ξ", answer)
        self.assertEqual(match_local_template("柯西中值定理")["id"], "cauchy_mean_value")

    def test_topology_answer_contains_mapping_proof(self):
        answer = local_math_answer("为什么连续函数把紧集映射为紧集？")
        self.assertIn("f⁻¹", answer)
        self.assertIn("有限子覆盖", answer)

    def test_unknown_question_is_honest(self):
        answer = local_math_answer("一个非常特殊的问题")
        self.assertIn("模型暂不可用", answer)

    def test_common_analysis_templates(self):
        self.assertIn("紧集", local_math_answer("连续函数在紧集上有界的原因"))
        self.assertIn("介值定理", local_math_answer("证明介值定理"))


if __name__ == "__main__":
    unittest.main()
