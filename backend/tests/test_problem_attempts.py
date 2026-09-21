import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.problem_attempts import list_attempts, review_attempt, submit_attempt
from app.database import Base
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept
from app.models.concept import Concept


class ProblemAttemptTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        problem = Problem(title="极值", content="求 x^2 的最小值", solution="0", difficulty="基础")
        self.db.add(problem)
        self.db.commit()
        self.problem_id = problem.id

    def tearDown(self):
        self.db.close()

    def test_submission_is_unverified_until_review(self):
        submitted = submit_attempt(self.problem_id, {"answer": "x=0"}, self.db)
        self.assertEqual(submitted["correctness"], "unverified")
        self.assertEqual(submitted["status"], "submitted")
        reviewed = review_attempt(submitted["id"], {"correctness": "correct", "feedback": "结论正确。", "independent": True}, self.db)
        self.assertEqual(reviewed["status"], "reviewed")
        self.assertEqual(reviewed["independent"], "yes")
        self.assertEqual(list_attempts(self.problem_id, self.db)["items"][0]["correctness"], "correct")

    def test_empty_answer_is_rejected(self):
        with self.assertRaises(Exception):
            submit_attempt(self.problem_id, {"answer": "  "}, self.db)


if __name__ == "__main__":
    unittest.main()
