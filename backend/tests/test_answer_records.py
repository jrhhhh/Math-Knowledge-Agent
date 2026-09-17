import unittest
from fastapi.testclient import TestClient
from app.main import app

class AnswerRecordContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_answer_list_contract(self):
        response = self.client.get("/ai/answers?limit=1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())

    def test_feedback_validation_and_missing_answer(self):
        invalid = self.client.post("/ai/answers/999999/feedback", json={"rating": 6})
        self.assertEqual(invalid.status_code, 422)
        missing = self.client.post("/ai/answers/999999/feedback", json={"rating": 5})
        self.assertEqual(missing.status_code, 404)

if __name__ == "__main__":
    unittest.main()
