import time
import unittest

import app.api.ai as ai


class CacheBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.original = dict(ai._answer_cache)
        ai._answer_cache.clear()

    def tearDown(self):
        ai._answer_cache.clear()
        ai._answer_cache.update(self.original)

    def test_version_invalidation_rejects_old_answer(self):
        value = {"answer": "cached"}
        ai._answer_cache["q"] = {"at": time.monotonic(), "version": ai._knowledge_version, "value": value}
        self.assertEqual(ai.cached_answer("Q"), value)
        ai.invalidate_answer_cache()
        self.assertIsNone(ai.cached_answer("q"))

    def test_expired_answer_is_removed(self):
        ai._answer_cache["old"] = {"at": time.monotonic() - ai._ANSWER_CACHE_TTL - 1, "version": ai._knowledge_version, "value": {"answer": "old"}}
        self.assertIsNone(ai.cached_answer("old"))
        self.assertNotIn("old", ai._answer_cache)


if __name__ == "__main__":
    unittest.main()
