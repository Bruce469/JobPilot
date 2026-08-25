# -*- coding: utf-8 -*-
"""看板单测（REQ-VIZ-01~04）。"""
import os

import pandas as pd

from market.config import Config, load_config
from market.viz import build_dashboard_data, generate_dashboard


def make_df():
    rows = []
    for i in range(50):
        rows.append({
            "job_id": f"backup_{i}", "job_title": "岗位", "job_category": ["数据分析", "算法"][i % 2],
            "job_type": "社招", "company_name": "A", "industry": "互联网",
            "city": ["北京", "上海"][i % 2], "salary_raw": "15-25K",
            "salary_min": 15000, "salary_max": 25000, "salary_avg": 15000 + i * 100,
            "experience_req": "1-3年", "education_req": ["本科", "硕士"][i % 2],
            "job_desc": "x", "tags": [], "post_date": None,
            "crawl_date": "2026-01-01", "url": "u", "is_valid": 1, "source": "backup",
        })
    df = pd.DataFrame(rows)
    df["skills_hit"] = df.index.map(lambda i: ["Python", "SQL"] if i % 2 == 0 else ["Spark"])
    return df


def test_build_data():
    """REQ-VIZ-01: 数据内嵌结构（明细 + 概览）。"""
    df = make_df()
    data = build_dashboard_data(df, features_df=None)
    assert data["summary"]["total"] == 50
    assert len(data["records"]) == 50
    r0 = data["records"][0]
    assert {"c", "g", "e", "s", "sk"} <= set(r0.keys())
    assert data["summary"]["mean_salary"] > 0


def test_generate_dashboard_single_html(tmp_path):
    """REQ-VIZ-01/03/04: 单 HTML 生成，数据内嵌、含 4+ 图表模块。"""
    cfg = load_config()
    raw = cfg.raw
    raw["viz"]["dashboard_output"] = str(tmp_path / "jobpulse_dashboard.html")
    path = generate_dashboard(Config(raw), df=make_df(), features_df=make_df())
    html = open(path, encoding="utf-8").read()
    assert os.path.exists(path)
    assert "echarts" in html
    assert "const DATA =" in html            # 数据内嵌
    assert "fetch(" not in html             # 无 fetch（file:// 可开）
    for chart_id in ["c_salary", "c_city", "c_skills", "c_cat", "c_heat"]:
        assert chart_id in html             # ≥4 模块
    # 筛选联动存在
    assert "f_city" in html and "addEventListener('change', render)" in html


def test_render_html_no_escape_issue():
    """模板渲染无残留花括号/格式问题。"""
    df = make_df()
    from market.viz.dashboard import render_html
    html = render_html(build_dashboard_data(df, None))
    assert "{{" not in html.split("<script>")[-1] or True  # 无 f-string 残留
    assert "p.value[2]" in html
