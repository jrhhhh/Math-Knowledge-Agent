import unittest
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app


class APIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_contract(self):
        response = self.client.get("/ai/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn("success_rate", response.json())
        self.assertIn("retry_queue", response.json())
        self.assertIn("request_logs_deleted", response.json())

    def test_retry_validation_contract(self):
        response = self.client.post("/ai/retry-queue", json={"operation": "unsupported", "question": "x"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("detail", response.json())

    def test_missing_retry_job_contract(self):
        response = self.client.get("/ai/retry-queue/not-found")
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())

    def test_stream_error_event_contract(self):
        response = self.client.post("/ai/ask-stream", json={"question": ""})
        self.assertEqual(response.status_code, 200)
        self.assertIn('"error_code": "http_error"', response.text)

    def test_concurrent_stream_connections(self):
        def request_stream(_):
            response = self.client.post("/ai/ask-stream", json={"question": ""})
            return response.status_code, '"error_code": "http_error"' in response.text

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(request_stream, range(16)))
        self.assertTrue(all(status == 200 and valid for status, valid in results))


if __name__ == "__main__":
    unittest.main()
