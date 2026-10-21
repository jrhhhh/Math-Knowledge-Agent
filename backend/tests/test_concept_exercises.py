import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.concept_exercises import GenerateRequest, ExerciseContent, generate_exercises, adopt_draft, list_drafts
from app.api.problem_attempts import submit_attempt
from app.api.problems import get_problems
from app.database import Base
from app.models.concept import Concept
from app.models.concept_exercise import ConceptExerciseDraft
from app.models.concept_learning_progress import ConceptLearningProgress
from app.models.knowledge_source import KnowledgeDocument, KnowledgeChunk
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept
from app.models.problem_source import ProblemSource


class ConceptExerciseTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.concept = Concept(name='有理数', description='两个整数之比，分母非零', field='数学分析')
        self.db.add(self.concept)
        self.db.commit()
        self.body = {'title': '有理数辨析', 'content': '说明为什么 \\(1/3\\) 是有理数。', 'solution': '分子1、分母3都是整数，且分母非零。'}

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def generate(self):
        with patch('app.api.concept_exercises.call_deepseek', return_value=json.dumps({'items': [self.body]})) as call:
            result = generate_exercises(GenerateRequest(concept_id=self.concept.id, count=1), self.db)
        return result, call.call_args.kwargs

    def test_generation_is_durable_draft_not_a_problem_or_mastery(self):
        result, args = self.generate()
        item = result['items'][0]
        self.assertEqual(item['status'], 'draft')
        self.assertEqual(item['mathematical_verification'], 'unverified')
        self.assertEqual(item['context']['concept']['id'], self.concept.id)
        self.assertEqual(item['context']['sources'], [])
        self.assertIn('有理数', args['messages'][1]['content'])
        self.assertEqual(len(list_drafts(self.concept.id, self.db)['items']), 1)
        self.assertEqual(self.db.query(Problem).count(), 0)
        self.assertEqual(self.db.query(ConceptLearningProgress).count(), 0)

    def test_only_reviewed_direct_sources_enter_generation(self):
        approved = KnowledgeDocument(title='已审教材', course='分析', review_status='approved')
        draft = KnowledgeDocument(title='草稿教材', course='分析', review_status='draft')
        self.db.add_all([approved, draft]); self.db.flush()
        for book, status, text, linked in [(approved, 'approved', '可用片段', True), (approved, 'unreviewed', '不可用甲', True), (draft, 'approved', '不可用乙', True), (approved, 'approved', '不可用丙', False)]:
            self.db.add(KnowledgeChunk(document_id=book.id, concept_id=self.concept.id if linked else None, content=text, page_start=34, page_end=35, review_status=status))
        self.db.commit()
        result, args = self.generate()
        context = result['items'][0]['context']
        self.assertEqual(len(context['sources']), 1)
        self.assertEqual(context['sources'][0]['excerpt'], '可用片段')
        self.assertNotIn('不可用', args['messages'][1]['content'])
        adopted = adopt_draft(result['items'][0]['id'], ExerciseContent(**self.body), self.db)
        self.assertEqual(self.db.query(ProblemSource).filter_by(problem_id=adopted['problem_id']).one().relation, 'inspired_by')

    def test_adoption_retains_edits_links_and_repeated_click_is_idempotent(self):
        result, _ = self.generate()
        draft_id = result['items'][0]['id']
        edited = ExerciseContent(**(self.body | {'title': '编辑后的题目'}))
        first = adopt_draft(draft_id, edited, self.db)
        second = adopt_draft(draft_id, edited, self.db)
        self.assertEqual(first['problem_id'], second['problem_id'])
        self.assertTrue(second['existing'])
        self.assertEqual(self.db.query(Problem).count(), 1)
        self.assertEqual(self.db.query(ProblemConcept).one().concept_id, self.concept.id)
        self.assertEqual(self.db.get(Problem, first['problem_id']).title, '编辑后的题目')
        self.assertEqual(get_problems(self.db)[0]['generation']['origin'], 'ai_generated')
        self.assertEqual(list_drafts(self.concept.id, self.db)['items'][0]['status'], 'adopted')
        attempt = submit_attempt(first['problem_id'], {'answer': '两个整数之比', 'independent': True}, self.db)
        self.assertEqual(attempt['correctness'], 'unverified')
        self.assertEqual(self.db.query(ConceptLearningProgress).count(), 0)

    def test_invalid_or_partial_provider_reply_saves_nothing(self):
        for reply in ['', '{}', 'not json', json.dumps({'items': [self.body | {'solution': ' '}]}), json.dumps({'items': [self.body, self.body]})]:
            with self.subTest(reply=reply), patch('app.api.concept_exercises.call_deepseek', return_value=reply):
                with self.assertRaises(HTTPException) as error:
                    generate_exercises(GenerateRequest(concept_id=self.concept.id, count=1), self.db)
                self.assertEqual(error.exception.status_code, 502)
                self.assertEqual(self.db.query(ConceptExerciseDraft).count(), 0)
        with patch('app.api.concept_exercises.call_deepseek', side_effect=TimeoutError('private provider diagnostics')):
            with self.assertRaises(HTTPException) as error:
                generate_exercises(GenerateRequest(concept_id=self.concept.id), self.db)
            self.assertEqual(error.exception.status_code, 503)
            self.assertNotIn('private', error.exception.detail)

    def test_missing_concept_and_input_bounds(self):
        with patch('app.api.concept_exercises.call_deepseek') as call:
            with self.assertRaises(HTTPException) as error:
                generate_exercises(GenerateRequest(concept_id=99999), self.db)
            self.assertEqual(error.exception.status_code, 404)
            call.assert_not_called()
        for extra in [{'count': 0}, {'count': 6}, {'count': True}, {'difficulty': '随便'}, {'objective': 'a' * 601}]:
            with self.assertRaises(ValidationError):
                GenerateRequest(concept_id=self.concept.id, **extra)
        with self.assertRaises(ValidationError):
            ExerciseContent(title=' ', content='题目', solution='解答')


if __name__ == '__main__':
    unittest.main()
