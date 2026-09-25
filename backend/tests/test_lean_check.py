import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from app.ai.lean_check import check_known_theorem


class LeanCheckTests(unittest.TestCase):
    def test_registered_theorem_is_formally_verified(self):
        with patch("app.ai.lean_check.shutil.which", return_value="/usr/bin/lean"), patch(
            "app.ai.lean_check.subprocess.run",
            return_value=CompletedProcess(["lean", "Check.lean"], 0, "", ""),
        ):
            result = check_known_theorem("nat_add_zero")
        self.assertEqual(result["status"], "formally_verified")
        self.assertEqual(result["evidence_type"], "formal_verification")

    def test_missing_lean_is_reported_without_false_verification(self):
        with patch("app.ai.lean_check.shutil.which", return_value=None):
            result = check_known_theorem("nat_add_zero")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "lean_not_found")

    def test_unknown_theorem_is_rejected(self):
        with self.assertRaises(ValueError):
            check_known_theorem("user_supplied_code")


if __name__ == "__main__":
    unittest.main()
