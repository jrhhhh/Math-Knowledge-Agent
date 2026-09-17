import unittest

from fastapi.testclient import TestClient

from app.main import app


class TemplateAPIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_template_list_and_validation(self):
        response = self.client.get("/local-templates?enabled=true")
        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())
        invalid = self.client.post("/local-templates", json={"template_id": "", "pattern": "x", "answer": "y"})
        self.assertEqual(invalid.status_code, 422)
        invalid_pattern = self.client.post("/local-templates", json={"template_id": "bad-pattern", "pattern": "[", "answer": "x"})
        self.assertEqual(invalid_pattern.status_code, 422)
        invalid_content = self.client.post("/local-templates", json={"template_id": "bad-content", "pattern": "x", "answer": "<script>alert(1)</script>"})
        self.assertEqual(invalid_content.status_code, 422)

    def test_template_stats_contract(self):
        response = self.client.get("/local-templates/stats")
        self.assertEqual(response.status_code, 200)
        self.assertIn("by_status", response.json())

    def test_template_usage_contract(self):
        response = self.client.get("/local-templates/usage")
        self.assertEqual(response.status_code, 200)
        self.assertIn("total_hits", response.json())

    def test_template_recommendations_contract(self):
        response = self.client.get("/local-templates/recommendations")
        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())

    def test_template_ab_test_validation_contract(self):
        response = self.client.post("/local-templates/ab-test", json={"template_ids": ["a", "b"], "questions": ["测试"]})
        self.assertEqual(response.status_code, 404)

    def test_sample_stats_contract(self):
        response = self.client.get("/local-templates/samples/stats")
        self.assertEqual(response.status_code, 200)
        self.assertIn("by_template", response.json())

    def test_template_preview_contract(self):
        response = self.client.post("/local-templates/preview", json={"question": "不存在的模板问题"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("matched", response.json())

    def test_template_export_import_contract(self):
        exported = self.client.get("/local-templates/export")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("items", exported.json())
        imported = self.client.post("/local-templates/import", json={"items": [{"template_id": "ci-template", "pattern": "ci", "answer": "CI"}]})
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.json()["total"], 1)
        self.assertEqual(imported.json()["created"] + imported.json()["updated"], 1)

    def test_review_endpoint_contract(self):
        response = self.client.post("/local-templates/ci-template/review?status=approved")
        self.assertIn(response.status_code, (200, 404))

    def test_template_events_contract(self):
        response = self.client.get("/local-templates/not-found/events")
        self.assertEqual(response.status_code, 200)
        self.assertIn("events", response.json())

    def test_missing_template_rollback_contract(self):
        response = self.client.post("/local-templates/not-found/rollback/1")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
