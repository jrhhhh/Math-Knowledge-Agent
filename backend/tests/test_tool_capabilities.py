import unittest
from unittest.mock import patch

from app.ai.tool_capabilities import capability_snapshot


class ToolCapabilityTests(unittest.TestCase):
    def test_snapshot_has_explicit_availability_and_disclaimer(self):
        with patch("app.ai.tool_capabilities.shutil.which", return_value=None):
            snapshot = capability_snapshot()
        self.assertIn("lean", snapshot["tools"])
        self.assertFalse(snapshot["tools"]["lean"]["available"])
        self.assertIn("不表示", snapshot["disclaimer"])


if __name__ == "__main__":
    unittest.main()
