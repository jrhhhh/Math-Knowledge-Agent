import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BACKEND_DIR / "math_agent.db"


def database_url_from_environment() -> str:
    """Return a stable SQLite URL, independent of the process working directory.

    ``MATH_AGENT_DB_PATH`` is shared with the backup and restore scripts, so an
    operator can move durable data without having the web app and maintenance
    commands accidentally operate on different database files.
    """
    configured_path = os.getenv("MATH_AGENT_DB_PATH")
    db_path = Path(configured_path).expanduser() if configured_path else DEFAULT_DB_PATH
    db_path = db_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


DATABASE_URL = database_url_from_environment()


engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False
    }
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()
