import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.agent_verification_report import AgentVerificationReport
from app.models.agent_task_event import AgentTaskEvent
from app.models.ai_task_status import AITaskStatus


class AgentModeReportTests(unittest.TestCase):
    def test_ask_agent_mode_persists_tool_report(self):
        result = {"answer": "42", "answer_source": "test", "answer_quality": {"score": 1, "correctness_status": "unverified", "checks": {}, "formula": {"valid": True, "issues": []}}, "knowledge_sources": [], "concepts": [], "historical_problems": [], "similar_problems": [], "knowledge_graph": {"nodes": [], "relations": []}, "formula_fixes": []}
        with patch("app.api.ai.call_deepseek", return_value=result["answer"]):
            response = TestClient(app).post("/ai/ask", json={"question": "使用 Lean 形式化检查", "agent_mode": True, "agent_parameters": {"theorem": "nat_add_zero"}})
        self.assertEqual(response.status_code, 200)
        request_id = response.json()["request_id"]
        db = SessionLocal()
        try:
            report = db.query(AgentVerificationReport).filter_by(request_id=request_id).one()
            self.assertEqual(report.status, "formally_verified")
        finally:
            db.query(AgentTaskEvent).filter_by(request_id=request_id).delete(synchronize_session=False)
            db.query(AITaskStatus).filter_by(request_id=request_id).delete(synchronize_session=False)
            db.query(AgentVerificationReport).filter_by(request_id=request_id).delete(synchronize_session=False)
            db.commit()
            db.close()
