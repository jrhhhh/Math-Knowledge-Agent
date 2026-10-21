import unittest
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.api.concept_exercises import thinking_hint
from app.models.problem import Problem
from app.models.problem_hint import ProblemHint


class ThinkingHintTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.problem = Problem(title='无理性', content='证明根号2不是有理数', solution='PRIVATE_SOLUTION')
        self.db.add(self.problem); self.db.commit()

    def tearDown(self):
        self.db.close(); self.engine.dispose()

    def test_model_receives_question_without_solution(self):
        with patch('app.api.concept_exercises.call_deepseek', return_value='先设根号2为既约分数，再比较分子分母的奇偶性。') as call:
            result = thinking_hint(self.problem.id, self.db)
        self.assertEqual(result['source'], 'deepseek')
        self.assertNotIn('PRIVATE_SOLUTION', str(call.call_args))

    def test_reviewed_hint_avoids_model_call(self):
        self.db.add(ProblemHint(problem_id=self.problem.id, level=1, content='先设既约分数。', review_status='approved'))
        self.db.commit()
        with patch('app.api.concept_exercises.call_deepseek') as call:
            self.assertEqual(thinking_hint(self.problem.id, self.db)['source'], 'curated')
            call.assert_not_called()

    def test_missing_problem_or_incomplete_hint(self):
        with self.assertRaises(HTTPException) as error:
            thinking_hint(99999, self.db)
        self.assertEqual(error.exception.status_code, 404)
        with patch('app.api.concept_exercises.call_deepseek', return_value=''):
            with self.assertRaises(HTTPException) as error:
                thinking_hint(self.problem.id, self.db)
            self.assertEqual(error.exception.status_code, 503)
