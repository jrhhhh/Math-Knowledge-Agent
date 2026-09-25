import unittest

from app.ai.lean_check import check_known_theorem


class LeanCheckTests(unittest.TestCase):
    def test_registered_theorem_is_formally_verified(self):
        result = check_known_theorem("nat_add_zero")
        self.assertEqual(result["status"], "formally_verified")
        self.assertEqual(result["evidence_type"], "formal_verification")

    def test_unknown_theorem_is_rejected(self):
        with self.assertRaises(ValueError):
            check_known_theorem("user_supplied_code")


if __name__ == "__main__":
    unittest.main()
