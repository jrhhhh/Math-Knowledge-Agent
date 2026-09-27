import unittest

from app.ai.exact_calculus import differentiate_polynomial, integrate_polynomial_definite, verify_polynomial_identity, polynomial_latex
from app.ai.exact_math import ExactMathError


class ExactCalculusTests(unittest.TestCase):
    def test_latex_display_preserves_rational_coefficient_and_power(self):
        self.assertEqual(polynomial_latex("x^12/3"), r"\frac{1}{3}\cdot x^{12}")
        result = integrate_polynomial_definite("x^12", 0, 1)
        self.assertEqual(result["value"], "1/13")
        self.assertEqual(result["antiderivative_latex"], r"\frac{1}{13}\cdot x^{13}")

    def test_identity_compares_all_coefficients(self):
        result = verify_polynomial_identity("(x+1)^2", "x²+2x+1")
        self.assertEqual(result["status"], "symbolically_verified")
        self.assertEqual(result["difference"], "0")
        false_identity = verify_polynomial_identity("x*(x-1)", "0")
        self.assertEqual(false_identity["status"], "identity_disproved")
        self.assertEqual(false_identity["difference"], "x**2 - x")

    def test_identity_endpoint_does_not_erase_domain_restrictions(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        for left, right in (("x/x", "1"), ("sin(x)^2+cos(x)^2", "1"), ("x**13", "x**13"), ("__import__('os')", "0")):
            with self.subTest(left=left):
                response = client.post("/ai/tools/polynomial-identity", json={"left": left, "right": right})
                self.assertEqual(response.status_code, 422)
                self.assertNotIn("symbolically_verified", response.text)
        supported = client.post("/ai/tools/polynomial-identity", json={"left": "x/2+x/2", "right": "x"})
        self.assertEqual(supported.status_code, 200)
        self.assertTrue(supported.json()["identity"])

    def test_derivative_uses_exact_polynomial_rules(self):
        result = differentiate_polynomial("x^3 + 2x - 1")
        self.assertEqual(result["derivative"], "3*x**2 + 2")
        self.assertEqual(result["evidence_type"], "symbolic_derivative")

    def test_definite_integral_returns_exact_rational_and_antiderivative(self):
        result = integrate_polynomial_definite("3x^2 + 2x + 1", "0", "1")
        self.assertEqual(result["value"], "3")
        self.assertEqual(result["antiderivative"], "x**3 + x**2 + x")

    def test_integral_of_square_is_one_third(self):
        result = integrate_polynomial_definite("x²", 0, 1)
        self.assertEqual(result["value"], "1/3")
        self.assertEqual(result["tool_version"], "1.0.0")
        self.assertEqual(result["input"]["expression"], "x²")
        self.assertEqual(result["resource_limits"]["max_degree"], 12)

    def test_rational_bounds_and_reversed_interval_are_exact(self):
        forward = integrate_polynomial_definite("x", "0", "1/2")
        reverse = integrate_polynomial_definite("x", "1/2", "0")
        self.assertEqual(forward["value"], "1/8")
        self.assertEqual(reverse["value"], "-1/8")

    def test_rejects_non_polynomial_or_unsafe_constructs(self):
        for expression in ("1/x", "sin(x)", "x**13", "x**x", "__import__('os')"):
            with self.subTest(expression=expression), self.assertRaises(ExactMathError):
                differentiate_polynomial(expression)


if __name__ == "__main__":
    unittest.main()
