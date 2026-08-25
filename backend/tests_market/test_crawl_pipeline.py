# -*- coding: utf-8 -*-
"""采集主流程集成自测（REQ-DC-03 增量幂等）：
对同一源重复运行两次 → jobs 记录数不增加，job_snapshots 按批次增加。
"""
import os
from datetime import datetime

import pytest

from market.config import Config, load_config
from market.crawler.pipeline import run_crawl
from market.storage import count_jobs, count_snapshots
from market.storage.session import reset_engine


@pytest.fixture(scope="module")
def mini_dataset(tmp_path_factory):
    """迷你数据集（2 行，含 1 条城市=其他）。"""
    import pandas as pd

    rows = [
        {"jobname": "数据分析师", "company": "公司A", "salary": "(15000.0, 25000.0)",
         "city": "北京", "description": "本科及以上学历", "other": "五险一金",
         "label": "数据分析", "minsalary": 15000, "maxsalary": 25000, "meansalary": 20000,
         "city_idx": 0},
        {"jobname": "算法工程师", "company": "公司B", "salary": "(20000.0, 40000.0)",
         "city": "其他", "description": "硕士学历", "other": "", "label": "算法岗",
         "minsalary": 20000, "maxsalary": 40000, "meansalary": 30000, "city_idx": 1},
    ]
    f = tmp_path_factory.mktemp("data") / "mini.csv"
    pd.DataFrame(rows).to_csv(f, index=False)
    return f


@pytest.fixture
def cfg_with_dataset(mini_dataset, tmp_path_factory):
    """SQLite 配置 + 指向迷你数据集。"""
    cfg = load_config()
    raw = cfg.raw
    raw["database"] = {
        "driver": "sqlite",
        "sqlite_path": str(tmp_path_factory.mktemp("db") / "crawl.db"),
        "password_env": "", "password_default": "",
    }
    raw["crawler"]["backup_dataset"] = str(mini_dataset)
    raw["crawler"]["alert_hit_rate"] = 0.30
    return Config(raw)


@pytest.fixture(autouse=True)
def _fresh(cfg_with_dataset):
    reset_engine()
    from market.storage import init_db

    init_db(cfg_with_dataset, drop_first=True)
    yield
    reset_engine()


class TestCrawlPipeline:
    def test_first_run(self, cfg_with_dataset):
        """首次运行：2 行写入，1 条有效，快照 2 行。"""
        r = run_crawl(cfg_with_dataset, source="backup", crawl_date=datetime(2026, 1, 1))
        assert r.jobs_total == 2
        assert r.valid_total == 1
        assert count_jobs(cfg_with_dataset) == 1  # valid_only 默认
        assert count_jobs(cfg_with_dataset, valid_only=False) == 2
        assert count_snapshots(cfg_with_dataset) == 2

    def test_second_run_idempotent(self, cfg_with_dataset):
        """REQ-DC-03: 第二次运行（新批次）→ jobs 不增，快照 +2。"""
        run_crawl(cfg_with_dataset, source="backup", crawl_date=datetime(2026, 1, 1))
        run_crawl(cfg_with_dataset, source="backup", crawl_date=datetime(2026, 1, 8))
        assert count_jobs(cfg_with_dataset, valid_only=False) == 2   # 不增
        assert count_snapshots(cfg_with_dataset) == 4                # 快照按批次增加

    def test_same_batch_same_snapshot(self, cfg_with_dataset):
        """同批次内重复导入：快照去重（(job_id, crawl_date) 唯一）。"""
        run_crawl(cfg_with_dataset, source="backup", crawl_date=datetime(2026, 1, 1))
        run_crawl(cfg_with_dataset, source="backup", crawl_date=datetime(2026, 1, 1))
        assert count_snapshots(cfg_with_dataset) == 2

    def test_monitor_report(self, cfg_with_dataset):
        """REQ-DC-07: 监控统计行产出。"""
        r = run_crawl(cfg_with_dataset, source="backup", crawl_date=datetime(2026, 1, 1))
        assert len(r.monitor_rows) >= 1
        total_hits = sum(x["hits"] for x in r.monitor_rows)
        assert total_hits == 2
