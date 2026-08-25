# -*- coding: utf-8 -*-
"""全局配置加载器（REQ-DB-02 / 7.4 配置管理）。

从 market/config/config.yaml 读取配置，DB 密码优先从环境变量注入。
合并后：默认 SQLite，sqlite_path 指向宿主 A 的 data/app.db（WAL 下两套访问层共存），
可用 APP_DB_PATH 环境变量覆盖（与 A 的 config.py 同一机制）。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent          # backend/
PACKAGE_DIR = Path(__file__).resolve().parent                  # backend/market/
DEFAULT_CONFIG_PATH = PACKAGE_DIR / "config" / "config.yaml"


def _load_dotenv(path: Path) -> None:
    """手动加载 .env（KEY=VALUE 每行；已存在的环境变量不覆盖）。

    避免引入 python-dotenv 依赖；.env 不入 git（.gitignore 已含）。
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class Config:
    """配置容器：属性访问 + 环境变量注入 DB 密码"""

    def __init__(self, data: dict[str, Any]):
        self._data = data

    def __getattr__(self, item: str) -> Any:
        try:
            return self._data[item]
        except KeyError:
            raise AttributeError(item)

    @property
    def raw(self) -> dict[str, Any]:
        return self._data

    def database(self) -> dict[str, Any]:
        """数据库配置，含解析后的密码（仅从环境变量/.env 读取，不硬编码——需求 7.4）。

        未配置密码时（MySQL 驱动）抛 ValueError 引导设置 DB_PASSWORD。
        """
        db = dict(self._data["database"])
        pw_env = db.get("password_env") or "DB_PASSWORD"
        _load_dotenv(PROJECT_ROOT / ".env")
        password = os.environ.get(pw_env, "")
        if not password and db.get("driver") == "mysql":
            raise ValueError(
                f"未配置数据库密码：请设置环境变量 {pw_env}（或项目根 .env 文件），"
                f"或切换 database.driver=sqlite 开发兜底"
            )
        db["password"] = password
        return db

    def sqlalchemy_url(self) -> str:
        """SQLAlchemy 连接串：mysql+pymysql://... 或 sqlite:///...（REQ-DB-02）。

        密码经 URL 编码（含 @:/ 等特殊字符时连接串不破裂）。
        """
        from urllib.parse import quote_plus

        db = self.database()
        if db.get("driver") == "sqlite":
            # 与 A 共用同一库文件：优先环境变量 APP_DB_PATH（测试/冒烟用），
            # 否则按 config.yaml 的 sqlite_path（相对 backend/，默认 data/app.db）
            env_path = os.environ.get("APP_DB_PATH")
            path = Path(env_path) if env_path else PROJECT_ROOT / db.get("sqlite_path", "data/app.db")
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{path.as_posix()}"
        user = db["user"]
        password = quote_plus(db.get("password", ""))
        host = db.get("host", "localhost")
        port = db.get("port", 3306)
        name = db["name"]
        charset = db.get("charset", "utf8mb4")
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset={charset}"

    # ---- 便捷访问 ----
    @property
    def cities(self) -> list[str]:
        return list(self._data["crawler"]["cities"])

    @property
    def categories(self) -> dict[str, list[str]]:
        return dict(self._data["crawler"]["categories"])

    def save(self, path: str | Path | None = None) -> None:
        target = Path(path) if path else DEFAULT_CONFIG_PATH
        target.write_text(yaml.safe_dump(self._data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def load_config(path: str | Path | None = None) -> Config:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Config(data or {})
