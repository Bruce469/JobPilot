# -*- coding: utf-8 -*-
"""配置安全单测（需求 7.4：DB 密码仅环境变量注入，不硬编码）。"""
import os
from pathlib import Path

import pytest

from market.config import Config, _load_dotenv, load_config


def make_cfg(db_override: dict) -> Config:
    cfg = load_config()
    raw = cfg.raw
    raw["database"] = {**raw["database"], **db_override}
    return Config(raw)


class TestPasswordInjection:
    def test_mysql_without_password_raises(self):
        """MySQL 驱动未配置密码 → 明确报错（不再回退硬编码默认值）。"""
        cfg = make_cfg({"driver": "mysql", "password_env": "DB_PASSWORD",
                        "password_default": ""})
        # 确保环境变量未设置
        old = os.environ.pop("DB_PASSWORD", None)
        try:
            with pytest.raises(ValueError, match="DB_PASSWORD"):
                cfg.database()
        finally:
            if old is not None:
                os.environ["DB_PASSWORD"] = old

    def test_password_from_env(self, monkeypatch):
        monkeypatch.setenv("DB_PASSWORD", "s3cret")
        cfg = make_cfg({"driver": "mysql"})
        assert cfg.database()["password"] == "s3cret"

    def test_sqlite_no_password_needed(self, monkeypatch, tmp_path):
        """SQLite 兜底不要求密码（NFR-01 开发模式）。"""
        monkeypatch.delenv("DB_PASSWORD", raising=False)
        cfg = make_cfg({"driver": "sqlite", "sqlite_path": str(tmp_path / "x.db")})
        url = cfg.sqlalchemy_url()
        assert url.startswith("sqlite:///")

    def test_password_url_encoded(self, monkeypatch):
        """连接串中密码特殊字符（@:/）URL 编码，不破坏连接串。"""
        monkeypatch.setenv("DB_PASSWORD", "p@ss:w/rd")
        cfg = make_cfg({"driver": "mysql"})
        url = cfg.sqlalchemy_url()
        assert "p%40ss%3Aw%2Frd" in url
        assert "p@ss:w/rd@localhost" not in url  # 未编码则连接串破裂

    def test_no_password_in_config_yaml(self):
        """config.yaml 不含明文密码（安全审查修复项）。

        合并后配置迁至 backend/market/config/config.yaml。
        """
        text = (Path(__file__).resolve().parent.parent / "market" / "config" / "config.yaml").read_text(encoding="utf-8")
        assert "password_default" not in text
        assert "123456" not in text


class TestDotenv:
    def test_load_dotenv(self, tmp_path, monkeypatch):
        f = tmp_path / ".env"
        f.write_text("# comment\nDB_PASSWORD=from_dotenv\nEMPTY=\n", encoding="utf-8")
        monkeypatch.delenv("DB_PASSWORD", raising=False)
        _load_dotenv(f)
        assert os.environ.get("DB_PASSWORD") == "from_dotenv"

    def test_dotenv_not_override_existing(self, tmp_path, monkeypatch):
        f = tmp_path / ".env"
        f.write_text("DB_PASSWORD=new\n", encoding="utf-8")
        monkeypatch.setenv("DB_PASSWORD", "existing")
        _load_dotenv(f)
        assert os.environ["DB_PASSWORD"] == "existing"
