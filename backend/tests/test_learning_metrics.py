import unittest
from datetime import datetime,timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.api.learning_metrics import metric_snapshot,record_visit
from app.models.problem import Problem
from app.models.problem_attempt import ProblemAttempt
from app.models.answer_record import AnswerRecord,AnswerFeedback

class LearningMetricsTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=__import__('sqlalchemy.pool',fromlist=['StaticPool']).StaticPool);Base.metadata.create_all(self.engine);self.db=sessionmaker(bind=self.engine)();self.now=datetime(2026,10,10,8)
        self.problem=Problem(title='复习题',content='题目');self.db.add(self.problem);self.db.commit()
    def tearDown(self):self.db.close();self.engine.dispose()
    def add(self,offset,review_offset=None,independent='yes',parent=None):
        a=ProblemAttempt(problem_id=self.problem.id,answer='草稿',created_at=self.now-timedelta(hours=offset),reviewed_at=self.now-timedelta(hours=review_offset) if review_offset is not None else None,status='reviewed' if review_offset is not None else 'submitted',correctness='correct' if review_offset is not None else 'unverified',independent=independent,hint_level=0,parent_attempt_id=parent);self.db.add(a);self.db.commit();return a
    def test_empty_and_duplicate_visits(self):
        d=metric_snapshot(self.db,30,self.now);self.assertEqual(d['funnel']['submitted_problems'],0);self.assertIsNone(d['feedback']['median_review_wait_seconds'])
        self.assertEqual(record_visit(self.db)['id'],record_visit(self.db)['id'])
        actual=metric_snapshot(self.db,0);self.assertEqual(actual['visits']['active_days'],1);self.assertEqual(actual['visits']['recorded_return_days'],0)
    def test_feedback_must_precede_retest_and_revision_is_not_independent(self):
        a=self.add(72,71);self.add(70,69);b=self.add(24,23,parent=a.id);d=metric_snapshot(self.db,30,self.now)
        self.assertEqual(d['funnel']['repeated_after_feedback'],1);self.assertEqual(d['funnel']['delayed_independent_success'],0)
        self.add(0,0);d=metric_snapshot(self.db,30,self.now);self.assertEqual(d['funnel']['delayed_independent_success'],0) # last feedback only 23 h ago
    def test_delayed_reviewed_success_and_pending_not_success(self):
        self.add(72,71);self.add(30,None);d=metric_snapshot(self.db,30,self.now);self.assertEqual(d['funnel']['delayed_independent_success'],0)
        self.add(0,0);d=metric_snapshot(self.db,30,self.now);self.assertEqual(d['funnel']['delayed_independent_success'],1);self.assertEqual(d['feedback']['pending_attempts'],1)
        self.assertEqual(d['evidence'][0]['delayed_success_pairs'][0]['delay_seconds'],71*3600)
    def test_same_period_cohort_and_latest_rating_only(self):
        self.add(24*40,24*40-1);self.add(0,None);d=metric_snapshot(self.db,7,self.now);self.assertEqual(d['funnel']['reviewed_problems'],0)
        answer=AnswerRecord(request_id='x',question='q',answer='a',answer_source='test',created_at=self.now);self.db.add(answer);self.db.commit()
        self.db.add_all([AnswerFeedback(answer_id=answer.id,rating=5,created_at=self.now-timedelta(minutes=2)),AnswerFeedback(answer_id=answer.id,rating=1,created_at=self.now-timedelta(minutes=1))]);self.db.commit();d=metric_snapshot(self.db,7,self.now)
        self.assertEqual(d['feedback']['rated_answers'],1);self.assertEqual(d['feedback']['helpful_answers'],0)

    def test_http_query_values_and_visit_deduplication(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.learning_metrics import router,get_db
        app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:self.db
        with TestClient(app) as client:
            for days in (0,7,30):self.assertEqual(client.get(f'/learning/metrics?days={days}').status_code,200)
            self.assertEqual(client.get('/learning/metrics?days=8').status_code,422)
            self.assertEqual(client.post('/learning/visit').json(),client.post('/learning/visit').json())
