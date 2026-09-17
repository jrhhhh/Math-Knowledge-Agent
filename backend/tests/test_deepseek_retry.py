import unittest
from unittest.mock import patch
from types import SimpleNamespace

from openai import APIConnectionError, APITimeoutError

from app.api.ai import call_deepseek


class DeepSeekRetryTests(unittest.TestCase):
    @patch("app.api.ai.time.sleep")
    @patch("app.api.ai.client.chat.completions.create")
    def test_connection_error_retries_then_succeeds(self, create, sleep):
        create.side_effect = [APIConnectionError(request=None), SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ignored"))])]
        result = call_deepseek([], max_retries=2, retry_delay=0)
        self.assertEqual(result, "ignored")
        self.assertEqual(create.call_count, 2)
        sleep.assert_called_once()

    @patch("app.api.ai.time.sleep")
    @patch("app.api.ai.client.chat.completions.create")
    def test_timeout_exhaustion_is_propagated(self, create, sleep):
        create.side_effect = APITimeoutError(request=None)
        with self.assertRaises(APITimeoutError):
            call_deepseek([], max_retries=3, retry_delay=0)
        self.assertEqual(create.call_count, 3)
        self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
