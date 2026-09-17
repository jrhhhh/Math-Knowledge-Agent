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

    def test_evaluate_contract(self):
        response = self.client.post("/ai/evaluate", json={
            "question": "证明连续函数在紧集上有界",
            "answer": "设 K 为紧集。由连续函数在紧集上取界，故函数有界。",
            "knowledge_points": ["紧集", "连续函数"],
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("formula_valid", body)
        self.assertEqual(body["missing_points"], [])

if __name__ == "__main__":
    unittest.main()
