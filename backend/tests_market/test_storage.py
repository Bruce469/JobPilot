# -*- coding: utf-8 -*-
"""存储层自测（模块 A）：
- A1 market_jobs/market_job_snapshots models 与建表（可重复执行）
- A2 session 工厂：SQLite 兜底可用
- A3 幂等 upsert + 快照追加 + 失效标记（REQ-DB-03/04, REQ-SCHED-03）
验收标准：同一 job_id 重复写入 jobs 不增行；快照按批次追加；唯一索引生效。
"""
import os
from datetime import datetime

import pytest
from sqlalchemy import inspect

from market.config import Config, load_config
from market.storage import (
    count_jobs,
    count_snapshots,
    fetch_jobs_for_analysis,
    init_db,
    insert_snapshots,
    mark_invalid,
    upsert_jobs,
)
from market.storage.session import get_engine, reset_engine


@pytest.fixture(scope="module")
def sqlite_cfg(tmp_path_factory):
    """SQLite 兜底配置（隔离临时库文件）。"""
    db_file = tmp_path_factory.mktemp("db") / "test_jobpulse.db"
    cfg = load_config()
    raw = cfg.raw
    raw["database"] = {
        "driver": "sqlite",
        "sqlite_path": str(db_file),
        "password_env": "",
        "password_default": "",
    }
    return Config(raw)


@pytest.fixture(autouse=True)
def _fresh_db(sqlite_cfg):
    reset_engine()
    engine = init_db(sqlite_cfg, drop_first=True)
    yield engine
    reset_engine()


def make_job(job_id: str = "backup_1", crawl_date: datetime | None = None,
             salary_raw: str = "15-25K", is_valid: int = 1, **kw) -> dict:
    base = {
        "job_id": job_id,
        "job_title": "数据分析师",
        "job_category": "数据分析",
        "job_type": "社招",
        "company_name": "测试公司",
        "industry": "互联网",
        "company_size": "1000-5000人",
        "city": "北京",
        "salary_raw": salary_raw,
        "salary_min": 15000,
        "salary_max": 25000,
        "salary_avg": 20000,
        "experience_req": "1-3年",
        "education_req": "本科",
        "job_desc": "负责数据分析相关工作",
        "tags": ["五险一金"],
        "post_date": None,
        "crawl_date": crawl_date or datetime(2026, 1, 1, 10, 0, 0),
        "url": "http://example.com/job/1",
        "is_valid": is_valid,
        "source": "backup",
    }
    base.update(kw)
    return base


class TestBuildAndSchema:
    def test_tables_created(self, sqlite_cfg):
        """A1: 两张表均存在。"""
        insp = inspect(get_engine())
        tables = set(insp.get_table_names())
        assert {"market_jobs", "market_job_snapshots"} <= tables

    def test_jobs_unique_index(self, sqlite_cfg):
        """A3: job_id 为主键（幂等键）。"""
        insp = inspect(get_engine())
        pk = insp.get_pk_constraint("market_jobs")
        assert pk["constrained_columns"] == ["job_id"]

    def test_snapshot_unique_constraint(self, sqlite_cfg):
        """A3: market_job_snapshots 有 (job_id, crawl_date) 唯一约束。"""
        insp = inspect(get_engine())
        uqs = [u["column_names"] for u in insp.get_unique_constraints("market_job_snapshots")]
        assert ["job_id", "crawl_date"] in uqs

    def test_repeat_init_db_idempotent(self, sqlite_cfg):
        """A1: 重复建表不报错。"""
        init_db(sqlite_cfg)
        init_db(sqlite_cfg)
        insp = inspect(get_engine())
        assert {"market_jobs", "market_job_snapshots"} <= set(insp.get_table_names())


class TestUpsertIdempotency:
    def test_empty_analysis_df_has_columns(self, sqlite_cfg):
        """空表时 fetch_jobs_for_analysis 返回 0 行带列结构（看板 meta/summary 对空库不报错）。"""
        df = fetch_jobs_for_analysis(sqlite_cfg, valid_only=True)
        assert df.empty
        assert "job_id" in df.columns and "salary_avg" in df.columns

    def test_insert_then_count(self, sqlite_cfg):
        """A3: 首次写入 2 条。"""
        upsert_jobs([make_job("backup_1"), make_job("backup_2")], sqlite_cfg)
        assert count_jobs(sqlite_cfg) == 2

    def test_upsert_same_id_no_duplicate(self, sqlite_cfg):
        """A3: 同一 job_id 重复写入，jobs 记录数不增，字段更新为最新。"""
        upsert_jobs([make_job("backup_1", salary_raw="15-25K")], sqlite_cfg)
        upsert_jobs([make_job("backup_1", salary_raw="20-30K", salary_avg=25000)], sqlite_cfg)
        assert count_jobs(sqlite_cfg) == 1
        from sqlalchemy import select
        from market.storage.models import Job
        from market.storage.session import session_scope
        with session_scope(sqlite_cfg) as s:
            job = s.scalar(select(Job).where(Job.job_id == "backup_1"))
            assert job.salary_raw == "20-30K"
            assert job.salary_avg == 25000

    def test_snapshots_append_per_batch(self, sqlite_cfg):
        """A3: 每次采集批次追加快照，批次间不覆盖。"""
        d1 = datetime(2026, 1, 1, 10, 0, 0)
        d2 = datetime(2026, 1, 8, 10, 0, 0)
        upsert_jobs([make_job("backup_1", crawl_date=d1)], sqlite_cfg)
        insert_snapshots([{"job_id": "backup_1", "crawl_date": d1, "salary_min": 15000,
                           "salary_max": 25000, "salary_avg": 20000, "is_valid": 1,
                           "url": "u"}], sqlite_cfg)
        upsert_jobs([make_job("backup_1", crawl_date=d2)], sqlite_cfg)
        insert_snapshots([{"job_id": "backup_1", "crawl_date": d2, "salary_min": 15000,
                           "salary_max": 25000, "salary_avg": 20000, "is_valid": 1,
                           "url": "u"}], sqlite_cfg)
        assert count_snapshots(sqlite_cfg) == 2

    def test_snapshot_dedup_within_batch(self, sqlite_cfg):
        """A3: 同一批次内同 job_id 只写一行快照。"""
        d1 = datetime(2026, 1, 1, 10, 0, 0)
        rows = [
            {"job_id": "backup_1", "crawl_date": d1, "salary_min": 15000,
             "salary_max": 25000, "salary_avg": 20000, "is_valid": 1, "url": "u"},
            {"job_id": "backup_1", "crawl_date": d1, "salary_min": 15000,
             "salary_max": 25000, "salary_avg": 20000, "is_valid": 1, "url": "u2"},
        ]
        n = insert_snapshots(rows, sqlite_cfg)
        assert n == 1
        assert count_snapshots(sqlite_cfg) == 1


class TestMarkInvalid:
    def test_mark_invalid(self, sqlite_cfg):
        """REQ-SCHED-03: 失效标记 jobs is_valid=0 + 追加 is_valid=0 快照。"""
        upsert_jobs([make_job("backup_1"), make_job("backup_2")], sqlite_cfg)
        n = mark_invalid(["backup_1"], datetime(2026, 1, 2), sqlite_cfg)
        assert n == 1
        assert count_jobs(sqlite_cfg, valid_only=True) == 1
        assert count_jobs(sqlite_cfg, valid_only=False) == 2
        assert count_snapshots(sqlite_cfg) == 1
