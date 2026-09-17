import unittest

from app.ai.formula_validator import validate_formula


class FormulaValidatorTests(unittest.TestCase):
    def test_balanced_formula(self):
        self.assertTrue(validate_formula(r"$f(x)=x^2$ \[x\]")["valid"])

    def test_unbalanced_formula_reports_reason(self):
        result = validate_formula(r"$f(x)={x^2$")
        self.assertFalse(result["valid"])
        self.assertTrue(result["issues"])


if __name__ == "__main__":
    unittest.main()
