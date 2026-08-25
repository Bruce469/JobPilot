"""pytest 公共夹具：临时 SQLite + 迁移。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db  # noqa: E402


@pytest.fixture()
def app_db(tmp_path, monkeypatch):
    """每测试一个独立临时 DB，并执行迁移建表。"""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db.migrate()
    yield
