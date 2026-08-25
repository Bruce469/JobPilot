# -*- coding: utf-8 -*-
"""采集层自测（模块 C）：
- C1 反爬容错：UA 池 / 重试退避 / 403 不重试（REQ-DC-02）
- checkpoint 断点续爬（REQ-DC-04）
- 健康监控（REQ-DC-07）
- backup adapter 字段映射与清洗（REQ-DC-05/06）
"""
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest
import requests

from market.crawler import (
    BackupAdapter,
    BlockedError,
    Checkpoint,
    HealthMonitor,
    request_with_retry,
)
from market.crawler.backup import CITY_WHITELIST, _parse_tags, transform_row


# ---------------------------------------------------------------- C1 反爬

class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text
        self.headers = {}


def make_session(statuses, texts=None):
    """构造依次返回指定状态的假 session。"""
    texts = texts or [""] * len(statuses)
    calls = []

    class FakeSession:
        def request(self, method, url, **kwargs):
            calls.append(kwargs)
            status = statuses.pop(0)
            text = texts.pop(0)
            return FakeResponse(status, text)

        def close(self):
            pass

    return FakeSession(), calls


class TestHttpRetry:
    def test_403_not_retried(self):
        """REQ-DC-02: 403 不重试，立即抛 BlockedError。"""
        sess, calls = make_session([403])
        with pytest.raises(BlockedError):
            request_with_retry("http://x", retry_times=3, session=sess)
        assert len(calls) == 1  # 只请求 1 次

    def test_5xx_retried(self):
        """REQ-DC-02: 5xx 重试直到成功。"""
        sess, calls = make_session([500, 503, 200])
        resp = request_with_retry("http://x", retry_times=3, backoff=0.01, session=sess)
        assert resp.status_code == 200
        assert len(calls) == 3

    def test_all_fail_raises(self):
        sess, calls = make_session([500, 500, 500])
        with pytest.raises(RuntimeError):
            request_with_retry("http://x", retry_times=3, backoff=0.01, session=sess)
        assert len(calls) == 3

    def test_waf_marker_not_retried(self):
        """WAF 挑战页文本也视为封禁（不重试）。"""
        sess, calls = make_session([200, 200], ["aliyun_waf_page", "x"])
        with pytest.raises(BlockedError):
            request_with_retry("http://x", retry_times=3, session=sess)
        assert len(calls) == 1

    def test_ua_from_pool(self):
        """REQ-DC-02: 请求带 UA 池中的 UA。"""
        sess, calls = make_session([200])
        request_with_retry("http://x", session=sess)
        ua = calls[0]["headers"].get("User-Agent", "")
        assert ua.startswith("Mozilla")


# ---------------------------------------------------------------- checkpoint

class TestCheckpoint:
    def test_save_and_resume(self, tmp_path):
        """REQ-DC-04: 记录页码 → 重载可续爬。"""
        cp = Checkpoint(tmp_path, "backup")
        assert cp.get_page("北京×数据分析") == 0
        cp.mark_page_done("北京×数据分析", 3)
        cp2 = Checkpoint(tmp_path, "backup")
        assert cp2.get_page("北京×数据分析") == 3

    def test_no_backtrack(self):
        cp = Checkpoint(Path(__import__("tempfile").gettempdir()), "t")
        cp.data = {}
        cp.mark_page_done("k", 5)
        cp.mark_page_done("k", 3)  # 更小不更新
        assert cp.get_page("k") == 5

    def test_corrupt_file(self, tmp_path):
        f = tmp_path / "checkpoint_backup.json"
        f.write_text("{broken", encoding="utf-8")
        cp = Checkpoint(tmp_path, "backup")
        assert cp.get_page("x") == 0


# ---------------------------------------------------------------- 健康监控

class TestHealthMonitor:
    def test_summary_and_alert(self, caplog):
        """REQ-DC-07: 统计表 + 0 命中/低命中率告警。"""
        m = HealthMonitor(alert_hit_rate=0.30)
        m.record_request("北京", "数据分析", ok=True, hits=10)
        m.record_request("北京", "数据分析", ok=True, hits=0)
        m.record_request("苏州", "数据科学", ok=True, hits=0)  # 0 命中组合
        with caplog.at_level("WARNING"):
            text = m.report()
        assert "整体命中率" in text
        assert "告警" in text
        assert "苏州×数据科学" in text


# ---------------------------------------------------------------- backup adapter

def fake_row(**over):
    row = {
        "jobname": "数据分析师", "company": "测试公司",
        "salary": "(15000.0, 25000.0)", "city": "北京",
        "description": "本科及以上学历，3年以上经验，负责数据分析",
        "other": "年终奖，五险一金", "label": "数据分析",
        "minsalary": 15000, "maxsalary": 25000, "meansalary": 20000,
        "city_idx": 0,
    }
    row.update(over)
    return row


class TestBackupTransform:
    def test_basic_mapping(self):
        """REQ-DC-06: 字段映射正确。"""
        r = transform_row(1, fake_row(), datetime(2026, 1, 1))
        assert r["job_id"] == "backup_1"
        assert r["job_title"] == "数据分析师"
        assert r["company_name"] == "测试公司"
        assert r["city"] == "北京"
        assert r["salary_min"] == 15000 and r["salary_max"] == 25000
        assert r["job_category"] == "数据分析"
        assert r["source"] == "backup"
        assert r["is_valid"] == 1

    def test_city_outside_whitelist_invalid(self):
        """城市"其他"→ is_valid=0。"""
        r = transform_row(2, fake_row(city="其他"), datetime(2026, 1, 1))
        assert r["is_valid"] == 0

    def test_city_unknown_invalid(self):
        r = transform_row(3, fake_row(city="天津"), datetime(2026, 1, 1))
        assert r["is_valid"] == 0
        assert r["city"] == "天津"

    def test_salary_mianyi_kept_null(self):
        """规则 5: 面议保留记录薪资 NULL。"""
        r = transform_row(4, fake_row(salary="面议"), datetime(2026, 1, 1))
        assert r["is_valid"] == 1
        assert r["salary_min"] is None and r["salary_max"] is None

    def test_salary_anomaly_invalid(self):
        """规则 6: 异常薪资 is_valid=0。"""
        r = transform_row(5, fake_row(salary="(350000.0, 500000.0)"), datetime(2026, 1, 1))
        assert r["is_valid"] == 0

    def test_experience_education_parsed(self):
        """经验/学历从 JD 文本解析。"""
        r = transform_row(6, fake_row(description="本科学历及以上，3年以上经验"), datetime(2026, 1, 1))
        assert r["education_req"] == "本科"
        assert r["experience_req"] == "3年以上"

    def test_intern_type(self):
        r = transform_row(7, fake_row(jobname="数据分析实习生"), datetime(2026, 1, 1))
        assert r["job_type"] == "实习"

    def test_tags_and_industry(self):
        r = transform_row(8, fake_row(other="行业要求：互联网\n年终奖，五险一金"), datetime(2026, 1, 1))
        assert r["industry"] == "互联网"
        assert r["tags"] == ["年终奖", "五险一金"]

    def test_category_by_keyword(self):
        r = transform_row(9, fake_row(jobname="数据仓库开发工程师", label="数据分析"), datetime(2026, 1, 1))
        assert r["job_category"] == "BI数仓"

    def test_job_id_idempotent(self):
        """同一行号 → 同一 job_id（幂等）。"""
        a = transform_row(10, fake_row(), datetime(2026, 1, 1))
        b = transform_row(10, fake_row(), datetime(2026, 1, 1))
        assert a["job_id"] == b["job_id"] == "backup_10"


class TestBackupAdapterIntegration:
    def test_import_all_counts(self, tmp_path):
        """数据集导入生成 jobs+snapshots。"""
        import pandas as pd

        df = pd.DataFrame([fake_row(), fake_row(city="其他")])
        f = tmp_path / "mini.xlsx"
        df.to_excel(f, index=False)
        adapter = BackupAdapter(f)
        jobs, snaps = adapter.import_all(datetime(2026, 1, 1))
        assert len(jobs) == 2 and len(snaps) == 2
        assert jobs[0]["job_id"] == "backup_1"
        assert jobs[1]["is_valid"] == 0
        assert snaps[0]["job_id"] == "backup_1"

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            BackupAdapter(tmp_path / "nope.xlsx").load()
