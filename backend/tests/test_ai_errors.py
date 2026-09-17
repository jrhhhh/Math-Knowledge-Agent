import unittest

from app.api.ai import classify_ai_error, remaining_generation_timeout
from openai import APIConnectionError


class AIErrorMappingTests(unittest.TestCase):
    def test_timeout_and_format_errors(self):
        self.assertEqual(classify_ai_error(TimeoutError())[0], "timeout")
        self.assertEqual(classify_ai_error(ValueError("bad json"))[0], "invalid_response")

    def test_network_and_unknown_errors(self):
        self.assertEqual(classify_ai_error(APIConnectionError(request=None))[0], "network")
        self.assertEqual(classify_ai_error(RuntimeError("unexpected"))[0], "unknown")

    def test_generation_timeout_is_bounded_by_request_deadline(self):
        import time
        deadline = time.perf_counter() + 8
        self.assertLessEqual(remaining_generation_timeout(deadline, 70), 8)
        with self.assertRaises(TimeoutError):
            remaining_generation_timeout(time.perf_counter() - 1, 70)


if __name__ == "__main__":
    unittest.main()
