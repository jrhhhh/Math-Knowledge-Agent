import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from app.main import app


class AgentClaimTests(unittest.TestCase):
    def test_retraction_propagates_transitively_without_claiming_proof(self):
        with TestClient(app) as client:
            task = uuid4().hex
            client.post("/ai/agent/run", json={"question": "求导 x²", "request_id": task})
            endpoint = f"/ai/tasks/{task}/claims"
            a = client.post(endpoint, json={"statement": "f 在闭区间连续", "source": "用户假设"}).json()
            b = client.post(endpoint, json={"statement": "f 有界", "source": "待核验推论", "depends_on": [a["id"]]}).json()
            c = client.post(endpoint, json={"statement": "存在有限上界", "source": "待核验推论", "depends_on": [b["id"]]}).json()
            self.assertEqual(c["status"], "unverified")
            result = client.post(f'{endpoint}/{a["id"]}/retract', json={"reason": "连续性条件不成立"}).json()
            self.assertEqual(result["affected_ids"], [a["id"], b["id"], c["id"]])
            statuses = [item["status"] for item in client.get(endpoint).json()["items"]]
            self.assertEqual(statuses, ["retracted", "needs_review", "needs_review"])
            task_state = client.get(f"/ai/tasks/{task}").json()
            self.assertEqual(task_state["status"], "needs_review")
            self.assertEqual(task_state["termination_reason"], "claim_retracted")
            self.assertEqual(task_state["result"]["status_before_claim_review"], "completed_with_evidence")
            self.assertEqual(task_state["result"]["evidence"][0]["derivative"], "2*x")
            invalid = client.post(endpoint, json={"statement": "新推论", "source": "用户", "depends_on": [c["id"]]}).json()
            self.assertEqual(invalid["status"], "needs_review")
            self.assertEqual(client.post(endpoint, json={"statement": "非法依赖", "source": "用户", "depends_on": [999999999]}).status_code, 422)
