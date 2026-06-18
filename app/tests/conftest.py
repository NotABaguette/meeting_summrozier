"""Test configuration.

Must set environment BEFORE importing any application module, because the DB
engine and settings are created at import time.
"""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="mi_test_"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["DATA_DIR"] = str(_TMP / "data")
os.environ["MODEL_CACHE_DIR"] = str(_TMP / "models")
os.environ["OLLAMA_AUTO_PULL"] = "false"
os.environ["DIARIZATION_ENABLED"] = "false"

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    """Create tables and wipe meeting rows around each test."""
    from meeting_intel.config import get_settings
    from meeting_intel.db import init_db, session_scope
    from meeting_intel.models import Meeting

    get_settings().ensure_dirs()
    init_db()
    with session_scope() as session:
        session.query(Meeting).delete()
    yield
    with session_scope() as session:
        session.query(Meeting).delete()
