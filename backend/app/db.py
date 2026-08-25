"""SQLite 连接工厂 + 迁移执行器（ADR-1：标准库 sqlite3）。"""
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from . import config
from .util import now_iso

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def get_conn() -> sqlite3.Connection:
    """每操作/每事务一个短连接；WAL + 外键 + busy_timeout。"""
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _load_scripts() -> list[tuple[int, str, str]]:
    scripts = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        m = re.match(r"^(\d+)_", path.name)
        if m:
            scripts.append((int(m.group(1)), path.name, path.read_text(encoding="utf-8")))
    return scripts


def migrate() -> None:
    """启动时按编号升序执行未应用脚本（每条一个事务）；失败即中止不静默。"""
    with closing(get_conn()) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
        for version, name, sql in _load_scripts():
            if version in applied:
                continue
            with conn:  # 成功 commit / 异常 rollback
                for stmt in sql.split(";"):
                    if stmt.strip():
                        conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, now_iso()),
                )


def current_schema_version() -> int:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return row[0] or 0
