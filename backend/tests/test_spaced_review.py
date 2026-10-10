import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from app.api.learning import review_state

class SpacedReviewTests(unittest.TestCase):
    def attempt(self, index, day, correctness='correct', independent='yes', parent=None, hint=0):
        return SimpleNamespace(id=index,created_at=datetime(2026,1,1)+timedelta(days=day),correctness=correctness,independent=independent,parent_attempt_id=parent,hint_level=hint,feedback='反馈',first_error_step=1)
    def test_same_day_repetitions_do_not_grant_stable_mastery(self):
        data=review_state([self.attempt(1,0),self.attempt(2,.01),self.attempt(3,.02)],datetime(2026,1,2))
        self.assertEqual(data['independent_streak'],1)
        self.assertEqual(data['state'],'independent_complete')
        self.assertTrue(data['due'])
    def test_delayed_success_and_later_error(self):
        attempts=[self.attempt(1,0),self.attempt(2,1),self.attempt(3,7)]
        state=review_state(attempts,datetime(2026,1,9))
        self.assertEqual(state['state'],'stable')
        self.assertEqual(state['interval_days'],7)
        attempts.append(self.attempt(4,8,'incorrect'))
        state=review_state(attempts,datetime(2026,1,9))
        self.assertEqual(state['state'],'needs_review')
        self.assertTrue(state['due'])
        self.assertTrue(state['has_error_history'])
        self.assertEqual(state['independent_streak'],0)
    def test_revision_and_hint_are_assisted_even_if_independent_claimed(self):
        self.assertEqual(review_state([self.attempt(1,0,parent=2)])['state'],'hinted_complete')
        self.assertEqual(review_state([self.attempt(1,0,hint=1)])['state'],'hinted_complete')
    def test_pending_retest_keeps_reviewed_state(self):
        data=review_state([self.attempt(1,0,'incorrect'),self.attempt(2,1,'unverified')])
        self.assertTrue(data['pending_retest'])
        self.assertEqual(data['state'],'needs_review')
    def test_due_time_boundary(self):
        attempts=[self.attempt(1,0)]
        self.assertFalse(review_state(attempts,datetime(2026,1,1,23,59,59))['due'])
        self.assertTrue(review_state(attempts,datetime(2026,1,2))['due'])
        self.assertIsNone(review_state([self.attempt(1,0,'unverified')]))
