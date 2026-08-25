# -*- coding: utf-8 -*-
"""EDA 单测（REQ-EDA-01~03）：图表产出 + 洞察量化口径。"""
import pandas as pd
import pytest

from market.analysis.eda import compute_insights, run_eda, save_eda_json
from market.config import Config, load_config


def make_df():
    rows = []
    cities = ["北京", "上海", "广州"]
    cats = ["数据分析", "算法", "数据科学"]
    for i in range(60):
        rows.append({
            "job_id": f"backup_{i}", "job_title": "岗位", "job_category": cats[i % 3],
            "job_type": "实习" if i % 10 == 0 else "社招",
            "company_name": "公司", "industry": "互联网",
            "city": cities[i % 3], "salary_raw": "15-25K",
            "salary_min": 15000, "salary_max": 25000,
            "salary_avg": 15000 + i * 100,
            "experience_req": ["1-3年", "3-5年", "5-10年"][i % 3],
            "education_req": ["本科", "硕士", "博士"][i % 3],
            "job_desc": "x", "tags": [], "post_date": None,
            "crawl_date": "2026-01-01", "url": "u", "is_valid": 1, "source": "backup",
        })
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def sqlite_cfg(tmp_path_factory):
    cfg = load_config()
    raw = cfg.raw
    raw["database"] = {
        "driver": "sqlite", "sqlite_path": str(tmp_path_factory.mktemp("d") / "eda.db"),
        "password_env": "", "password_default": "",
    }
    raw["paths"]["charts_dir"] = str(tmp_path_factory.mktemp("charts"))
    raw["paths"]["reports_dir"] = str(tmp_path_factory.mktemp("reports"))
    return Config(raw)


class TestEDA:
    def test_run_eda_produces_charts(self, sqlite_cfg):
        """REQ-EDA-01/02: 产出 ≥6 张图（分布≥3、对比≥3）。"""
        result = run_eda(sqlite_cfg, make_df())
        charts = result["charts"]
        assert len(charts) >= 6
        dist = ["city_job_count", "category_dist", "industry_top"]
        comp = ["edu_salary", "exp_salary", "city_salary"]
        for k in dist + comp:
            assert k in charts
            # 图文件已生成
            import os
            assert os.path.exists(charts[k])

    def test_insights_min_5_with_numbers(self, sqlite_cfg):
        """REQ-EDA-03: ≥5 条量化结论，含数值与口径。"""
        insights = compute_insights(make_df())
        assert len(insights) >= 5
        for ins in insights:
            assert ins["title"] and ins["detail"]
            assert any(ch.isdigit() for ch in ins["detail"])  # 含具体数值
            assert "样本" in ins["detail"] or "口径" in ins["detail"]

    def test_save_eda_json(self, sqlite_cfg):
        result = run_eda(sqlite_cfg, make_df())
        p = save_eda_json(result, sqlite_cfg)
        import os
        assert os.path.exists(p)

    def test_empty_raises(self, sqlite_cfg):
        with pytest.raises(ValueError):
            run_eda(sqlite_cfg, pd.DataFrame())
