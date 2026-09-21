import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.problem_attempts import list_attempts, review_attempt, submit_attempt
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


if __name__ == "__main__":
    unittest.main()
