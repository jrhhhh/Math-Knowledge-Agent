import unittest
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app


class APIContractTests(unittest.TestCase):

    def test_schema_version_table_exists(self):
        from sqlalchemy import inspect
        from app.database import engine
        inspector = inspect(engine)
        self.assertIn("schema_versions", inspector.get_table_names())

    def test_integrity_report_contract(self):
        response = self.client.get("/maintenance/integrity")
        self.assertEqual(response.status_code, 200)
        self.assertIn("checks", response.json())
        preview = self.client.get("/maintenance/integrity/repair-preview?limit=5")
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.json()["read_only"])
        backups = self.client.get("/maintenance/backups?limit=1")
        self.assertEqual(backups.status_code, 200)
        self.assertIn("items", backups.json())
        backup_alert = self.client.post("/maintenance/backup-alert/notify")
        self.assertEqual(backup_alert.status_code, 200)
        self.assertIn("sent", backup_alert.json())
        status = self.client.get("/maintenance/backup-status")
        self.assertEqual(status.status_code, 200)
        self.assertIn("status", status.json())
        repair = self.client.post("/maintenance/integrity/repair", json={})
        self.assertEqual(repair.status_code, 422)
        prepared = self.client.post("/maintenance/integrity/repair/prepare", json={"orphan_relation_ids": [999999]})
        self.assertEqual(prepared.status_code, 200)
        token = prepared.json()["confirmation_token"]
        mismatch = self.client.post("/maintenance/integrity/repair", json={"confirmation_token": token, "orphan_relation_ids": [999998]})
        self.assertEqual(mismatch.status_code, 409)
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_contract(self):
        response = self.client.get("/ai/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn("success_rate", response.json())
        self.assertIn("retry_queue", response.json())
        health = response.json()
        self.assertIn("primary_model_configured", health)
        self.assertIn("primary_model", health)
        self.assertIn("primary_base_url", health)
        self.assertIn("primary_timeout_seconds", health)
        self.assertIn("request_budget_seconds", health)
        self.assertIn("providers", health)
        self.assertIn("primary", health["providers"])
        self.assertIn("backup", health["providers"])
        self.assertNotIn("api_key", health)
        self.assertIn("request_logs_deleted", response.json())

    def test_task_status_contract(self):
        from app.api.ai import set_task_status, _stream_results
        set_task_status("test-task-status", "generating", "测试阶段")
        response = self.client.get("/ai/tasks/test-task-status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "generating")
        self.assertEqual(response.json()["stage"], "测试阶段")
        _stream_results["test-task-status"] = {"value": {"answer": "恢复答案"}}
        recovered = self.client.get("/ai/tasks/test-task-status")
        self.assertEqual(recovered.json()["result"]["answer"], "恢复答案")
        _stream_results.pop("test-task-status", None)
        persisted = self.client.get("/ai/tasks/test-task-status")
        self.assertEqual(persisted.json()["status"], "generating")
        missing = self.client.get("/ai/tasks/not-found-task")
        self.assertEqual(missing.status_code, 404)
        listing = self.client.get("/ai/tasks?offset=0&limit=5")
        self.assertEqual(listing.status_code, 200)
        self.assertIn("items", listing.json())
        cleanup = self.client.post("/ai/tasks/cleanup?older_than_days=3650")
        self.assertEqual(cleanup.status_code, 200)
        from app.database import SessionLocal
        from app.models.ai_task_status import AITaskStatus
        db = SessionLocal()
        db.query(AITaskStatus).filter(AITaskStatus.request_id == "test-task-conflict").delete(synchronize_session=False)
        db.add(AITaskStatus(request_id="test-task-conflict", question="测试问题", status="generating", stage="生成中"))
        db.commit()
        db.close()
        retry_conflict = self.client.post("/ai/tasks/test-task-conflict/retry")
        self.assertEqual(retry_conflict.status_code, 409)

    def test_retry_validation_contract(self):
        response = self.client.post("/ai/retry-queue", json={"operation": "unsupported", "question": "x"})
        self.assertEqual(response.status_code, 422)
        alerts = self.client.get("/ai/retry-alerts?window_minutes=60")
        self.assertEqual(alerts.status_code, 200)
        self.assertIn("failed_count", alerts.json())
        self.assertIn("trend_by_hour", alerts.json())
        self.assertIn("provider_failure_rates", alerts.json())
        dashboard = self.client.get("/ai/ops-dashboard?window_minutes=60")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("average_quality", dashboard.json())
        self.assertIn("by_source", dashboard.json())
        self.assertIn("health", dashboard.json())
        exported_dashboard = self.client.get("/ai/ops-dashboard/export?window_minutes=60")
        self.assertEqual(exported_dashboard.status_code, 200)
        self.assertIn("text/csv", exported_dashboard.headers.get("content-type", ""))
        self.assertIn("detail", response.json())

    def test_missing_retry_job_contract(self):
        response = self.client.get("/ai/retry-queue/not-found")
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())

    def test_request_log_list_contract(self):
        response = self.client.get("/ai/requests?limit=2")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("items", payload)
        self.assertEqual(payload["limit"], 2)
        self.assertGreaterEqual(payload["total"], len(payload["items"]))

    def test_request_log_filters_and_export_contract(self):
        invalid_status = self.client.get("/ai/requests?status=unknown")
        self.assertEqual(invalid_status.status_code, 400)
        invalid_time = self.client.get("/ai/requests?since=not-a-date")
        self.assertEqual(invalid_time.status_code, 400)
        export = self.client.get("/ai/requests/export?status=failed")
        self.assertEqual(export.status_code, 200)
        self.assertIn("text/csv", export.headers.get("content-type", ""))
        self.assertIn("request_id,question,status", export.text)

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
