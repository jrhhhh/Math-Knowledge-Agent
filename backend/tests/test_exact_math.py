import unittest

from app.ai.exact_math import ExactMathError, check_identity, evaluate_exact


class ExactMathTests(unittest.TestCase):
    def test_bounded_expression_is_exact(self):
        result = evaluate_exact("(12 + 8) * 3 ** 2")
        self.assertEqual(result["value"], 180)
        self.assertTrue(result["exact"])

    def test_rejects_calls_and_names(self):
        with self.assertRaises(ExactMathError):
            evaluate_exact("__import__('os').getcwd()")

    def test_rejects_division_by_zero(self):
        with self.assertRaises(ExactMathError):
            evaluate_exact("1 / 0")

    def test_division_stays_exact(self):
        result = evaluate_exact("1 / 3")
        self.assertEqual(result["value"], "1/3")
        self.assertEqual(result["method"], "bounded_rational_ast")

    def test_finds_bounded_counterexample(self):
        result = check_identity("x ** 2", "x")
        self.assertEqual(result["status"], "counterexample_found")
        self.assertEqual(result["counterexample"]["x"], -10)

    def test_reports_limited_scope_when_no_counterexample(self):
        result = check_identity("x + 1", "1 + x", start=-3, end=3)
        self.assertEqual(result["status"], "no_counterexample_in_range")
