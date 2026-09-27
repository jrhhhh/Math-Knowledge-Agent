import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.ai import ProofAnalyzeRequest, analyze_proof
from app.database import Base


class ProofFallbackTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_unavailable_model_returns_local_structural_review(self):
        request = ProofAnalyzeRequest(
            question="证明连续映射把紧集映成紧集",
            proof="设 K 是紧集。由连续性，开覆盖的原像覆盖 K。因此可取有限子覆盖。",
        )
        with patch("app.api.ai.call_deepseek", side_effect=RuntimeError("provider unavailable")):
            result = analyze_proof(request, self.db)

        self.assertEqual(result["review_source"], "local_rule_fallback")
        self.assertFalse(result["valid"])
        self.assertTrue(result["steps"])
        self.assertIn("不构成数学正确性验证", result["summary"])


if __name__ == "__main__":
    unittest.main()
