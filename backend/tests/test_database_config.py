import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.database import DEFAULT_DB_PATH, database_url_from_environment


class DatabaseConfigurationTests(unittest.TestCase):
    def test_default_database_is_in_backend_directory(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(database_url_from_environment(), f"sqlite:///{DEFAULT_DB_PATH.resolve()}")

    def test_database_path_override_is_resolved_and_parent_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "durable" / "learning.db"
            with patch.dict(os.environ, {"MATH_AGENT_DB_PATH": str(path)}, clear=True):
                self.assertEqual(database_url_from_environment(), f"sqlite:///{path.resolve()}")
            self.assertTrue(path.parent.is_dir())
