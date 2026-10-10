import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.problem_attempts import list_attempts, recommend_next_problem, review_attempt, submit_attempt
from app.database import Base
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept
from app.models.concept import Concept
from app.models.problem_concept import ProblemConcept
from app.models.concept_learning_progress import ConceptLearningProgress


class ProblemAttemptTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        problem = Problem(title="极值", content="求 x^2 的最小值", solution="0", difficulty="基础")
        concept = Concept(name="极值", description="求函数的最小值", field="数学分析")
        self.db.add_all([problem, concept])
        self.db.commit()
        self.problem_id = problem.id
        self.concept_id = concept.id
        self.db.add(ProblemConcept(problem_id=problem.id, concept_id=concept.id))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_submission_is_unverified_until_review(self):
        submitted = submit_attempt(self.problem_id, {"answer": "x=0"}, self.db)
        self.assertEqual(submitted["correctness"], "unverified")
        self.assertEqual(submitted["status"], "submitted")
        reviewed = review_attempt(submitted["id"], {"correctness": "correct", "feedback": "结论正确。", "independent": True}, self.db)
        self.assertEqual(reviewed["status"], "reviewed")
        self.assertEqual(reviewed["independent"], "yes")
        progress = self.db.query(ConceptLearningProgress).filter_by(concept_id=self.concept_id).one()
        self.assertEqual(progress.status, "completed")
        self.assertEqual(reviewed["learning_update"]["updated_concept_ids"], [self.concept_id])
        self.assertEqual(list_attempts(self.problem_id, self.db)["items"][0]["correctness"], "correct")

    def test_empty_answer_is_rejected(self):
        with self.assertRaises(Exception):
            submit_attempt(self.problem_id, {"answer": "  "}, self.db)

    def test_revision_retains_prior_feedback_and_requires_same_problem(self):
        original = submit_attempt(self.problem_id, {"answer": "最小值是1"}, self.db)
        review_attempt(original["id"], {"correctness": "incorrect", "first_error_step": 1, "feedback": "检查 x=0"}, self.db)
        revised = submit_attempt(self.problem_id, {"answer": "x=0时为0", "parent_attempt_id": original["id"]}, self.db)
        self.assertEqual(revised["parent_attempt_id"], original["id"])
        self.assertEqual(revised["correctness"], "unverified")
        history = list_attempts(self.problem_id, self.db)["items"]
        self.assertEqual(history[1]["first_error_step"], 1)
        self.assertEqual(history[1]["feedback"], "检查 x=0")
        other = Problem(title="另一题", content="求1+1", solution="2")
        self.db.add(other)
        self.db.commit()
        with self.assertRaises(Exception):
            submit_attempt(other.id, {"answer": "2", "parent_attempt_id": original["id"]}, self.db)

    def test_model_analysis_does_not_grant_correctness(self):
        from unittest.mock import patch
        from app.api.problem_attempts import analyze_attempt
        original = submit_attempt(self.problem_id, {"answer": "x²≥0"}, self.db)
        with patch("app.api.ai.analyze_proof", return_value={"valid": True, "review_source": "model", "steps": []}):
            result = analyze_attempt(original["id"], self.db)
        self.assertTrue(result["analysis"]["valid"])
        self.assertEqual(result["correctness"], "unverified")
        self.assertEqual(self.db.query(ConceptLearningProgress).count(), 0)

    def test_invalid_first_error_does_not_change_review(self):
        original = submit_attempt(self.problem_id, {"answer": "1"}, self.db)
        with self.assertRaises(Exception):
            review_attempt(original["id"], {"correctness": "incorrect", "first_error_step": 0}, self.db)
        self.assertEqual(list_attempts(self.problem_id, self.db)["items"][0]["correctness"], "unverified")

    def test_recommendation_prefers_same_concept_retest(self):
        second = Problem(title="极值重测", content="再次求 x^2 的最小值", solution="0", difficulty="基础")
        self.db.add(second)
        self.db.commit()
        self.db.refresh(second)
        self.db.add(ProblemConcept(problem_id=second.id, concept_id=self.concept_id, relation="tests", importance=1.0))
        self.db.commit()
        result = recommend_next_problem(problem_id=self.problem_id, db=self.db)
        self.assertEqual(result["item"]["id"], second.id)
        self.assertIn("当前知识点", result["reason"])


if __name__ == "__main__":
    unittest.main()
