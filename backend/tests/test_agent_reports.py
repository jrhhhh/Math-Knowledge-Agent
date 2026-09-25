import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.api.ai import record_failed_path, record_verification
from app.models.agent_failed_path import AgentFailedPath
from app.models.agent_verification_report import AgentVerificationReport


class AgentReportTests(unittest.TestCase):
    def test_verification_and_failed_path_are_separate_records(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        try:
            record_verification(db, "task-1", {"evidence_type": "formal_verification", "status": "formally_verified", "theorem": "nat_add_zero"})
            record_failed_path(db, "task-1", "counterexample_search", "invalid_parameters")
            db.commit()
            self.assertEqual(db.query(AgentVerificationReport).count(), 1)
            self.assertEqual(db.query(AgentFailedPath).one().reason, "invalid_parameters")
        finally:
            db.close()
            engine.dispose()
