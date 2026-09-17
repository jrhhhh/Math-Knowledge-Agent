import unittest
import os
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
        stats = self.client.get("/ai/answers/stats")
        self.assertEqual(stats.status_code, 200)
        self.assertIn("quality_levels", stats.json())
        missing = self.client.get("/ai/answers/999999")
        self.assertEqual(missing.status_code, 404)
        filtered = self.client.get("/ai/answers?level=weak&offset=0&limit=1")
        self.assertEqual(filtered.status_code, 200)
        exported = self.client.get("/ai/answers/export?level=weak")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("text/csv", exported.headers.get("content-type", ""))

    def test_feedback_contract_for_saved_answer(self):
        from app.database import SessionLocal
        from app.models.answer_record import AnswerRecord
        db = SessionLocal()
        try:
            item = AnswerRecord(request_id="test-feedback", question="q", answer="a", answer_source="test")
            db.add(item)
            db.commit()
            db.refresh(item)
            response = self.client.post(f"/ai/answers/{item.id}/feedback", json={"rating": 5, "feedback": "清晰"})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["rating"], 5)
            reviews = self.client.get("/ai/reviews")
            self.assertEqual(reviews.status_code, 200)
            reviewed = self.client.post(f"/ai/answers/{item.id}/review", json={"status": "false_positive", "note": "已核对"})
            self.assertEqual(reviewed.status_code, 200)
            self.assertEqual(reviewed.json()["status"], "false_positive")
            events = self.client.get(f"/ai/answers/{item.id}/review-events")
            self.assertEqual(events.status_code, 200)
            self.assertEqual(events.json()["total"], 1)
        finally:
            db.close()

    def test_admin_key_protects_review(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {"MATH_AGENT_ADMIN_KEY": "test-secret"}):
            denied = self.client.post("/ai/answers/999999/review", json={"status": "fixed"})
            self.assertEqual(denied.status_code, 403)

    def test_admin_login_returns_bearer_token(self):
        from unittest.mock import patch
        from app import security
        security._login_failures.clear()
        with patch.dict(os.environ, {"MATH_AGENT_ADMIN_KEY": "test-secret"}):
            invalid = self.client.post("/ai/auth/login", json={"key": "bad"})
            self.assertEqual(invalid.status_code, 401)
            valid = self.client.post("/ai/auth/login", json={"key": "test-secret"})
            self.assertEqual(valid.status_code, 200)
            self.assertEqual(valid.json()["token_type"], "bearer")

    def test_admin_login_rate_limit(self):
        from unittest.mock import patch
        from app import security
        security._login_failures.clear()
        with patch.dict(os.environ, {"MATH_AGENT_ADMIN_KEY": "test-secret"}):
            for _ in range(5):
                self.assertEqual(self.client.post("/ai/auth/login", json={"key": "wrong"}).status_code, 401)
            limited = self.client.post("/ai/auth/login", json={"key": "wrong"})
            self.assertEqual(limited.status_code, 429)
            events = self.client.get("/ai/security-events?limit=5")
            self.assertEqual(events.status_code, 200)
            self.assertIn("items", events.json())
            filtered = self.client.get("/ai/security-events?event=login_failed&ip=127.0.0.1")
            self.assertEqual(filtered.status_code, 200)
            alerts = self.client.get("/ai/security-alerts")
            self.assertEqual(alerts.status_code, 200)
            self.assertIn("alerts", alerts.json())
            no_webhook = self.client.post("/ai/security-alerts/notify", headers={"X-Admin-Key": "test-secret"})
            self.assertEqual(no_webhook.status_code, 503)

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

    def test_answer_retry_queue_contract(self):
        response = self.client.post("/ai/retry-queue", json={"operation": "answer", "question": "证明连续函数有界", "priority": 0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["operation"], "answer")

if __name__ == "__main__":
    unittest.main()
