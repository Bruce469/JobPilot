# -*- coding: utf-8 -*-
"""数据质量报告单测（REQ-DQ-03）。"""
import pandas as pd

from market.etl.quality_report import compute_quality_stats, render_markdown


def make_df():
    rows = [
        {"job_id": "backup_1", "job_title": "数据分析师", "job_category": "数据分析",
         "job_type": "社招", "company_name": "A", "industry": "互联网",
         "company_size": "1000-5000人", "city": "北京", "salary_raw": "15-25K",
         "salary_min": 15000, "salary_max": 25000, "salary_avg": 20000,
         "experience_req": "1-3年", "education_req": "本科", "job_desc": "x",
         "tags": [], "post_date": None, "crawl_date": "2026-01-01", "url": "u",
         "is_valid": 1, "source": "backup"},
        {"job_id": "backup_2", "job_title": "算法工程师", "job_category": "算法",
         "job_type": "实习", "company_name": "B", "industry": "金融",
         "company_size": None, "city": "上海", "salary_raw": "200-300元/天",
         "salary_min": 4000, "salary_max": 6000, "salary_avg": 5000,
         "experience_req": "1年以内", "education_req": "不限", "job_desc": "y",
         "tags": None, "post_date": None, "crawl_date": "2026-01-01", "url": "u",
         "is_valid": 1, "source": "backup"},
        {"job_id": "backup_3", "job_title": "数据分析师", "job_category": "数据分析",
         "job_type": "不限", "company_name": "C", "industry": "互联网",
         "company_size": None, "city": "其他", "salary_raw": "面议",
         "salary_min": None, "salary_max": None, "salary_avg": None,
         "experience_req": "不限", "education_req": "不限", "job_desc": "z",
         "tags": None, "post_date": None, "crawl_date": "2026-01-01", "url": "u",
         "is_valid": 0, "source": "backup"},
    ]
    return pd.DataFrame(rows)


class TestQualityStats:
    def test_counts(self):
        df = make_df()
        s = compute_quality_stats(df)
        assert s["total"] == 3
        assert s["valid"] == 2
        assert s["mianyi_count"] == 1
        assert s["salary_null_count"] == 1
        assert s["salary_anomaly_count"] == 0

    def test_field_missing_rate(self):
        df = make_df()
        s = compute_quality_stats(df)
        assert s["field_missing"]["company_size"] == round(2 / 3, 4)
        assert s["field_missing"]["city"] == 0.0
        assert s["field_missing"]["post_date"] == 1.0

    def test_intern_stats(self):
        df = make_df()
        s = compute_quality_stats(df)
        assert s["intern_stats"]["count"] == 1
        assert s["intern_stats"]["mean"] == 5000.0

    def test_render_contains_sections(self):
        df = make_df()
        s = compute_quality_stats(df)
        md = render_markdown(s, "2026-01-01 10:00:00")
        assert "# JobPulse 数据质量报告" in md
        assert "字段缺失率" in md
        assert "面议数量" in md
        assert "实习薪资单列统计" in md
        assert "2026-01-01 10:00:00" in md
