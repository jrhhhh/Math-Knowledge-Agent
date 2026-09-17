import unittest

from app.ai.answer_quality import evaluate_answer


class AnswerQualityTests(unittest.TestCase):
    def test_complete_proof_scores_well(self):
        result = evaluate_answer("定理：若 f 连续，则有结论。证明：由定义可得 f(x)=x。")
        self.assertEqual(result["level"], "good")
        self.assertTrue(result["checks"]["has_formula"])

    def test_empty_answer_is_weak(self):
        self.assertEqual(evaluate_answer("")["level"], "weak")


if __name__ == "__main__":
    unittest.main()
