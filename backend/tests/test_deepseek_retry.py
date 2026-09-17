import unittest
from unittest.mock import patch
from types import SimpleNamespace

from openai import APIConnectionError, APITimeoutError
from openai import APIStatusError, RateLimitError
import httpx2

from app.api.ai import call_deepseek


class DeepSeekRetryTests(unittest.TestCase):
    @staticmethod
    def status_error(error_type, status):
        request = httpx2.Request("POST", "https://api.deepseek.com")
        response = httpx2.Response(status, request=request)
        return error_type("mock failure", response=response, body={})

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

    @patch("app.api.ai.time.sleep")
    @patch("app.api.ai.client.chat.completions.create")
    def test_rate_limit_retries(self, create, sleep):
        create.side_effect = [self.status_error(RateLimitError, 429), self.status_error(RateLimitError, 429)]
        with self.assertRaises(RateLimitError):
            call_deepseek([], max_retries=2, retry_delay=0)
        self.assertEqual(create.call_count, 2)

    @patch("app.api.ai.time.sleep")
    @patch("app.api.ai.client.chat.completions.create")
    def test_server_error_retries_but_client_error_does_not(self, create, sleep):
        create.side_effect = [self.status_error(APIStatusError, 500), self.status_error(APIStatusError, 400)]
        with self.assertRaises(APIStatusError):
            call_deepseek([], max_retries=3, retry_delay=0)
        self.assertEqual(create.call_count, 2)


if __name__ == "__main__":
    unittest.main()
