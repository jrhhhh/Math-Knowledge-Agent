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


if __name__ == "__main__":
    unittest.main()
