import unittest

from app.ai.answer_quality import evaluate_answer


class AnswerQualityTests(unittest.TestCase):
    def test_complete_proof_scores_well(self):
        result = evaluate_answer("定理：若 f 连续，则有结论。证明：由定义可得 f(x)=x。")
        self.assertEqual(result["level"], "good")
        self.assertTrue(result["checks"]["has_formula"])

    def test_empty_answer_is_weak(self):
        self.assertEqual(evaluate_answer("")["level"], "weak")

    def test_proof_question_has_specialized_checks(self):
        result = evaluate_answer("设 x∈K。由定理可得，因此结论成立。证明完毕。", "证明连续函数在紧集上有界")
        self.assertEqual(result["question_type"], "proof")
        self.assertIn("has_basis", result["checks"])
        self.assertIn("has_derivation", result["checks"])


if __name__ == "__main__":
    unittest.main()
