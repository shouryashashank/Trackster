import os
import sys
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import db  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every test at a fresh, temporary SQLite database."""
    db_path = os.path.join(str(tmp_path), "trackster.db")
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    yield db


@pytest.fixture
def music_dir(tmp_path):
    """A per-test music output directory, ending with a slash like the app uses."""
    d = str(tmp_path / "music")
    os.makedirs(d, exist_ok=True)
    return d + os.sep
