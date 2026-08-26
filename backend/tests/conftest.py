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


@pytest.fixture(autouse=True)
def _isolate_offline_layers():
    """A股离线库（company_info_data.json）随构建脚本增量变化，测试统一清空索引保证隔离；
    test_company_info.py 等需要索引的用例自行注入。"""
    from app.fetcher import company_info
    company_info._INDEX = {}
    yield
