import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.ai import (
    GraphCandidateUpdateRequest,
    RelatedGraphRequest,
    generate_ai_related_graph,
    get_graph_candidate_events,
    get_related_graph,
    save_graph_candidate,
    update_graph_candidate,
    validate_graph_candidate,
)
from app.api.concepts import AliasRequest, LearningProgressRequest, add_concept_alias, get_concept_network, get_learning_path, get_learning_progress, search_concepts, set_learning_progress
from app.database import Base
from app.models.concept import Concept
from app.models.concept_relation import ConceptRelation
from app.models.graph_candidate import GraphCandidate


class GraphWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    @staticmethod
    def graph_payload():
        return {
            "nodes": [
                {"id": "n1", "name": "柯西中值定理", "type": "theorem"},
                {"id": "n2", "name": "拉格朗日中值定理", "type": "theorem"},
                {"id": "n3", "name": "可导条件", "type": "property"},
            ],
            "edges": [
                {"source": "n2", "target": "n1", "relation": "generalizes", "weight": 0.9},
                {"source": "n3", "target": "n1", "relation": "uses", "weight": 0.8},
            ],
        }

    def test_alias_matches_once_and_ai_node_reuses_concept(self):
        concept = Concept(name="紧集", type="concept", field="拓扑学")
        self.db.add(concept)
        self.db.commit()
        self.db.refresh(concept)
        add_concept_alias(concept.id, AliasRequest(alias="紧性"), self.db)

        from app.api.ai import safe_semantic_retrieve_concepts

        matches = safe_semantic_retrieve_concepts(self.db, "紧性是否具有有限子覆盖")
        self.assertEqual([item["concept"].id for item in matches], [concept.id])

        payload = {"nodes": [{"id": "n1", "name": "紧性", "type": "concept"}, {"id": "n2", "name": "开覆盖", "type": "concept"}], "edges": []}
        with patch("app.api.ai.call_deepseek", return_value=json.dumps(payload, ensure_ascii=False)):
            result = generate_ai_related_graph(self.db, "紧性")
        node = next(node for node in result["knowledge_graph"]["nodes"] if node["name"] == "紧集")
        self.assertEqual(node["id"], concept.id)
        self.assertEqual(node["source"], "knowledge_base")

    def test_candidate_validation_save_and_idempotency(self):
        semantic = {"valid": True, "confidence": 0.94, "issues": [], "invalid_edges": []}
        with patch("app.api.ai.call_deepseek", side_effect=[json.dumps(self.graph_payload()), json.dumps(semantic)]):
            generated = generate_ai_related_graph(self.db, "柯西中值定理")
            checked = validate_graph_candidate(generated["candidate_id"], self.db)
        self.assertEqual(checked["status"], "validated")
        first = save_graph_candidate(generated["candidate_id"], self.db)
        second = save_graph_candidate(generated["candidate_id"], self.db)
        self.assertEqual(first["created_concepts"], 3)
        self.assertEqual(first["created_relations"], 2)
        self.assertEqual(second["created_concepts"], 0)
        self.assertEqual(second["created_relations"], 0)
        events = get_graph_candidate_events(generated["candidate_id"], self.db)["events"]
        self.assertEqual([event["action"] for event in events], ["generated", "validated", "saved"])

    def test_low_confidence_candidate_cannot_be_saved(self):
        semantic = {"valid": True, "confidence": 0.61, "issues": ["方向不确定"], "invalid_edges": []}
        with patch("app.api.ai.call_deepseek", side_effect=[json.dumps(self.graph_payload()), json.dumps(semantic)]):
            generated = generate_ai_related_graph(self.db, "柯西中值定理")
            checked = validate_graph_candidate(generated["candidate_id"], self.db)
        self.assertEqual(checked["status"], "rejected")
        with self.assertRaises(HTTPException) as error:
            save_graph_candidate(generated["candidate_id"], self.db)
        self.assertEqual(error.exception.status_code, 409)

    def test_semantic_validation_failure_returns_503_and_records_error(self):
        with patch("app.api.ai.call_deepseek", return_value=json.dumps(self.graph_payload())):
            generated = generate_ai_related_graph(self.db, "柯西中值定理")
        with patch("app.api.ai.validate_graph_semantics", side_effect=RuntimeError("provider returned empty response")):
            with self.assertRaises(HTTPException) as error:
                validate_graph_candidate(generated["candidate_id"], self.db)
        self.assertEqual(error.exception.status_code, 503)
        candidate = self.db.query(GraphCandidate).filter_by(id=generated["candidate_id"]).one()
        self.assertEqual(candidate.status, "needs_review")
        events = get_graph_candidate_events(candidate.id, self.db)["events"]
        self.assertEqual(events[-1]["action"], "validation_failed")
        self.assertIn("provider returned empty response", events[-1]["detail"]["error"])

    def test_edit_resets_validation_and_cache_reuses_candidate(self):
        payload = self.graph_payload()
        with patch("app.api.ai.call_deepseek", return_value=json.dumps(payload)) as mocked:
            first = get_related_graph(RelatedGraphRequest(question="柯西中值定理"), self.db)
            second = get_related_graph(RelatedGraphRequest(question="柯西中值定理"), self.db)
        self.assertEqual(first["candidate_id"], second["candidate_id"])
        self.assertEqual(mocked.call_count, 1)
        edited = dict(payload)
        edited["nodes"] = payload["nodes"][:2]
        edited["edges"] = payload["edges"][:1]
        updated = update_graph_candidate(first["candidate_id"], GraphCandidateUpdateRequest(graph=edited), self.db)
        self.assertEqual(updated["status"], "pending")

    def test_relation_priority_replaces_lower_priority_edge(self):
        source = Concept(name="对象", type="concept")
        target = Concept(name="定理", type="theorem")
        self.db.add_all([source, target])
        self.db.commit()
        self.db.refresh(source)
        self.db.refresh(target)
        self.db.add(ConceptRelation(source_concept_id=source.id, target_concept_id=target.id, relation="supports", weight=0.6))
        self.db.commit()
        payload = {"nodes": [{"id": "n1", "name": "对象", "type": "concept"}, {"id": "n2", "name": "定理", "type": "theorem"}], "edges": [{"source": "n1", "target": "n2", "relation": "defines", "weight": 0.95}]}
        semantic = {"valid": True, "confidence": 0.95, "issues": [], "invalid_edges": []}
        with patch("app.api.ai.call_deepseek", side_effect=[json.dumps(payload), json.dumps(semantic)]):
            candidate = generate_ai_related_graph(self.db, "对象与定理")
            validate_graph_candidate(candidate["candidate_id"], self.db)
        save_graph_candidate(candidate["candidate_id"], self.db)
        relations = self.db.query(ConceptRelation).filter_by(source_concept_id=source.id, target_concept_id=target.id).all()
        self.assertEqual([(relation.relation, relation.weight) for relation in relations], [("defines", 0.95)])
        events = get_graph_candidate_events(candidate["candidate_id"], self.db)["events"]
        conflict = next(event for event in events if event["action"] == "relation_conflict")
        self.assertEqual(conflict["detail"]["action"], "replaced")

    def test_learning_path_is_prerequisite_first_and_cycle_safe(self):
        basics = Concept(name="集合", type="concept")
        topology = Concept(name="拓扑空间", type="concept")
        compactness = Concept(name="紧致性", type="concept")
        self.db.add_all([basics, topology, compactness])
        self.db.commit()
        self.db.add_all([
            ConceptRelation(source_concept_id=basics.id, target_concept_id=topology.id, relation="prerequisite", weight=0.8),
            ConceptRelation(source_concept_id=topology.id, target_concept_id=compactness.id, relation="prerequisite", weight=0.9),
            ConceptRelation(source_concept_id=compactness.id, target_concept_id=topology.id, relation="prerequisite", weight=0.1),
        ])
        self.db.commit()

        path = get_learning_path(compactness.id, max_depth=4, db=self.db)
        self.assertEqual([step["name"] for step in path["steps"]], ["集合", "拓扑空间", "紧致性"])
        self.assertEqual(path["steps"][-1]["stage"], "focus")
        self.assertTrue(path["cycle_detected"])

    def test_learning_progress_is_persisted_per_local_profile(self):
        concept = Concept(name="开集", type="concept")
        self.db.add(concept)
        self.db.commit()
        completed = set_learning_progress(concept.id, LearningProgressRequest(status="completed"), self.db)
        self.assertEqual(completed["status"], "completed")
        self.assertIsNotNone(completed["completed_at"])
        progress = get_learning_progress(db=self.db)
        self.assertEqual(progress["completed_concept_ids"], [concept.id])
        self.assertEqual(progress["summary"]["percent"], 100)
        self.assertEqual(progress["summary"]["next_concepts"], [])
        learning = set_learning_progress(concept.id, LearningProgressRequest(status="learning"), self.db)
        self.assertIsNone(learning["completed_at"])

    def test_persisted_concepts_can_be_searched_and_loaded_as_network(self):
        source = Concept(name="连续性", type="concept", field="分析学", description="函数连续的基本性质")
        target = Concept(name="紧致性", type="concept", field="拓扑学", description="有限子覆盖性质")
        self.db.add_all([source, target])
        self.db.commit()
        self.db.add(ConceptRelation(source_concept_id=source.id, target_concept_id=target.id, relation="supports", weight=0.8))
        self.db.commit()
        results = search_concepts("紧致", 12, self.db)
        self.assertEqual([item["name"] for item in results["items"]], ["紧致性"])
        network = get_concept_network(target.id, self.db)
        self.assertEqual({item["name"] for item in network["nodes"]}, {"连续性", "紧致性"})
        self.assertEqual(network["edges"][0]["relation"], "supports")


if __name__ == "__main__":
    unittest.main()
