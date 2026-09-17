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

    def test_only_one_recovery_probe_is_allowed(self):
        import app.ai.circuit_breaker as breaker
        breaker._opened_at = breaker.time.monotonic() - breaker._cooldown - 1
        breaker._half_open = False
        breaker._failures = 3
        breaker.before_call()
        self.assertEqual(snapshot()["state"], "half_open")
        with self.assertRaises(CircuitOpenError):
            breaker.before_call()
        breaker.success()
        self.assertEqual(snapshot()["state"], "closed")


if __name__ == "__main__":
    unittest.main()
