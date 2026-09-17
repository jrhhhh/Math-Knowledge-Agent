import unittest

from app.ai.circuit_breaker import CircuitOpenError, before_call, failure, success, snapshot


class CircuitBreakerTests(unittest.TestCase):
    def setUp(self):
        success()

    def test_opens_after_three_failures_and_resets_on_success(self):
        self.assertEqual(snapshot()["state"], "closed")
        failure(); failure(); failure()
        self.assertEqual(snapshot()["state"], "open")
        with self.assertRaises(CircuitOpenError):
            before_call()
        success()
        before_call()
        self.assertEqual(snapshot()["failure_streak"], 0)


if __name__ == "__main__":
    unittest.main()
