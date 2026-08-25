# -*- coding: utf-8 -*-
"""存储层：建表初始化 + 幂等写入 + 快照（REQ-DB-01/03/04）。"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from market.config import Config
from market.storage.models import Base, Job, JobSnapshot
from market.storage.session import get_engine, get_session_factory, session_scope

# jobs 表非键字段（用于 upsert 更新最新状态）
JOB_UPDATE_COLUMNS = [
    "job_title", "job_category", "job_type", "company_name", "industry",
    "company_size", "city", "salary_raw", "salary_min", "salary_max",
    "salary_avg", "experience_req", "education_req", "job_desc", "tags",
    "post_date", "crawl_date", "url", "is_valid", "source",
]


def init_db(cfg: Config, drop_first: bool = False) -> Engine:
    """建表初始化（REQ-DB-01，合并后兼容模式）。

    生产环境：market_jobs / market_job_snapshots 由宿主 A 的迁移脚本
    002_market_jobs.sql 创建并记入 schema_migrations，此处 create_all 为幂等补建
    （checkfirst=IF NOT EXISTS，与迁移机制不冲突），供独立 CLI init-db 与隔离测试库使用；
    drop_first=True 仅测试/重建用，绝不删 A 的业务表（metadata 不含 jobs/job_events）。
    """
    engine = get_engine(cfg)
    if drop_first:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return engine


def _upsert_stmt(model, rows: list[dict], update_cols: list[str]):
    """按方言构造 UPSERT 语句：MySQL ON DUPLICATE KEY UPDATE / SQLite ON CONFLICT DO UPDATE。"""
    engine = get_engine()
    if engine.dialect.name == "mysql":
        stmt = mysql_insert(model).values(rows)
        stmt = stmt.on_duplicate_key_update(
            **{c: getattr(stmt.inserted, c) for c in update_cols}
        )
        return stmt
    stmt = sqlite_insert(model).values(rows)
    pk_cols = [pk.name for pk in model.__table__.primary_key.columns]
    stmt = stmt.on_conflict_do_update(index_elements=pk_cols, set_={
        c: getattr(stmt.excluded, c) for c in update_cols
    })
    return stmt


def upsert_jobs(rows: list[dict], cfg: Config | None = None) -> int:
    """幂等写入 jobs 表：已存在则更新最新状态，不存在则插入（REQ-DB-03）。

    分批写入（chunk=40）兼容 SQLite 999 变量上限；返回总行数。
    """
    if not rows:
        return 0
    total = 0
    CHUNK = 40  # 40 行 × 21 列 = 840 变量 < SQLite 999 上限
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i + CHUNK]
        stmt = _upsert_stmt(Job, chunk, JOB_UPDATE_COLUMNS)
        with session_scope(cfg) as s:
            s.execute(stmt)
            total += len(chunk)
    return total


def insert_snapshots(rows: list[dict], cfg: Config | None = None) -> int:
    """追加快照：批次内按 (job_id, crawl_date) 先去重再写（REQ-DB-04）。

    跨批次/同批次重复导入时"存在则跳过"（INSERT IGNORE / ON CONFLICT DO NOTHING），
    保证幂等（REQ-DC-03）。返回本次实际写入行数。
    """
    if not rows:
        return 0
    # 批次内去重：同一 job_id + crawl_date 只保留一行
    seen: set[tuple] = set()
    deduped = []
    for r in rows:
        key = (r["job_id"], r["crawl_date"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    if not deduped:
        return 0
    engine = get_engine(cfg)
    if engine.dialect.name == "mysql":
        stmt = mysql_insert(JobSnapshot).prefix_with("IGNORE")
    else:
        stmt = sqlite_insert(JobSnapshot).on_conflict_do_nothing()
    total = 0
    CHUNK = 140  # 140 行 × 7 列 = 980 变量 < SQLite 999 上限
    for i in range(0, len(deduped), CHUNK):
        with session_scope(cfg) as s:
            s.execute(stmt, deduped[i:i + CHUNK])
            total += len(deduped[i:i + CHUNK])
    return total


def mark_invalid(job_ids: Iterable[str], crawl_date: datetime | None = None,
                 cfg: Config | None = None) -> int:
    """失效标记（REQ-SCHED-03）：jobs 置 is_valid=0 并记快照。返回标记数。"""
    ids = [j for j in job_ids if j]
    if not ids:
        return 0
    crawl_date = crawl_date or datetime.now()
    with session_scope(cfg) as s:
        existing: list[Job] = list(s.scalars(select(Job).where(Job.job_id.in_(ids))))
        for job in existing:
            job.is_valid = 0
        snaps = [
            JobSnapshot(job_id=j.job_id, crawl_date=crawl_date, is_valid=0,
                        salary_min=j.salary_min, salary_max=j.salary_max,
                        salary_avg=j.salary_avg, url=j.url)
            for j in existing
        ]
        if snaps:
            s.add_all(snaps)
        return len(existing)


def count_jobs(cfg: Config | None = None, valid_only: bool = True) -> int:
    """jobs 表计数（is_valid=1 口径为有效数；REQ-4.4）。"""
    with session_scope(cfg) as s:
        stmt = select(Job)
        if valid_only:
            stmt = stmt.where(Job.is_valid == 1)
        return len(list(s.scalars(stmt)))


def count_snapshots(cfg: Config | None = None) -> int:
    with session_scope(cfg) as s:
        return len(list(s.scalars(select(JobSnapshot))))


def fetch_jobs_for_analysis(cfg: Config | None = None, valid_only: bool = True):
    """导出 jobs 全量（供 ETL/EDA/建模），可选仅有效记录。

    空表时返回带列结构的空 DataFrame（避免看板 meta/summary 对空库报 KeyError——
    合并后首启动 market_jobs 为空是常态）。
    """
    import pandas as pd

    with session_scope(cfg) as s:
        stmt = select(Job)
        if valid_only:
            stmt = stmt.where(Job.is_valid == 1)
        rows = [dict(j.__dict__) for j in s.scalars(stmt)]
    for r in rows:
        r.pop("_sa_instance_state", None)
    if rows:
        return pd.DataFrame(rows)
    # 空表：返回 0 行但带完整列名的 DataFrame（避免看板 meta/summary 对空库报错且 total 不虚增）
    return pd.DataFrame(columns=[c.name for c in Job.__table__.columns])


def _test_clean(engine):
    """测试辅助：清空表。"""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
