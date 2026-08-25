# -*- coding: utf-8 -*-
"""技能图谱 NLP 单测（REQ-NLP-01/02/03/04/05）。"""
import os

import pandas as pd
import pytest

from market.config import Config, load_config
from market.nlp import (
    SkillMatcher,
    plot_skill_diff_heatmap,
    plot_top_skills,
    plot_wordcloud,
    save_features,
    skill_diff,
    top_skills,
)


@pytest.fixture(scope="module")
def matcher():
    return SkillMatcher()


@pytest.fixture(scope="module")
def cfg(tmp_path_factory):
    c = load_config()
    raw = c.raw
    raw["paths"]["charts_dir"] = str(tmp_path_factory.mktemp("charts"))
    raw["paths"]["features_path"] = str(tmp_path_factory.mktemp("f") / "features.parquet")
    return Config(raw)


def make_df():
    rows = []
    for i in range(40):
        desc = "熟悉Python、SQL、机器学习，会使用Spark和Tableau进行数据分析"
        if i % 3 == 0:
            desc += "，熟悉Hadoop大数据平台"
        if i % 5 == 0:
            desc += "，了解深度学习"
        rows.append({
            "job_id": f"backup_{i}", "job_title": "数据分析师", "job_category": "数据分析",
            "job_type": "社招", "company_name": "A", "industry": "互联网", "city": "北京",
            "salary_raw": "15-25K", "salary_min": 15000, "salary_max": 25000, "salary_avg": 20000,
            "experience_req": "1-3年", "education_req": "本科", "job_desc": desc,
            "tags": [], "post_date": None, "crawl_date": "2026-01-01", "url": "u",
            "is_valid": 1, "source": "backup",
        })
    return pd.DataFrame(rows)


class TestSkillMatcher:
    def test_word_count_50_plus(self, matcher):
        """REQ-NLP-02: 技能词表 50~100 个。"""
        assert 50 <= matcher.word_count <= 100, f"技能词表 {matcher.word_count} 个"

    def test_match_skills(self, matcher):
        hits = matcher.match_skills("熟悉Python、SQL，使用Spark做数据分析")
        assert "Python" in hits and "SQL" in hits and "Spark" in hits

    def test_case_insensitive(self, matcher):
        hits = matcher.match_skills("熟练使用python和spark")
        assert "Python" in hits and "Spark" in hits

    def test_no_match(self, matcher):
        assert matcher.match_skills("完全无关的内容") == []

    def test_compute_features(self, matcher):
        df = matcher.compute_features(make_df())
        assert "skills_hit" in df.columns and "skills_count" in df.columns
        assert (df["skills_count"] > 0).all()


class TestSkillAnalysis:
    def test_top_skills_ratio(self, matcher):
        """REQ-NLP-03: Top30 占比口径（命中岗位数/有效岗位总数）。"""
        df = matcher.compute_features(make_df())
        top = top_skills(df, matcher, top_k=30)
        assert len(top) <= 30
        assert "ratio" in top.columns
        assert top["ratio"].max() <= 1.0
        python_row = top[top["skill"] == "Python"]
        assert len(python_row) == 1
        assert python_row.iloc[0]["ratio"] == pytest.approx(1.0, abs=0.01)

    def test_skill_diff(self, matcher):
        df = matcher.compute_features(make_df())
        diff = skill_diff(df, matcher, group_col="job_category", top_n=5)
        assert isinstance(diff, dict) and len(diff) >= 1

    def test_plots_produced(self, matcher, cfg):
        """REQ-NLP-03/04: 排名图/差异图/词云产出。"""
        df = matcher.compute_features(make_df())
        top = top_skills(df, matcher, 30)
        p1 = plot_top_skills(top, cfg)
        p2 = plot_skill_diff_heatmap(skill_diff(df, matcher, "job_category", 5), cfg)
        p3 = plot_wordcloud(df, matcher, cfg)
        assert os.path.exists(p1) and os.path.exists(p2) and os.path.exists(p3)

    def test_save_features(self, matcher, cfg):
        """REQ-NLP-05: features.parquet 产出。"""
        df = matcher.compute_features(make_df())
        p = save_features(df, cfg)
        assert os.path.exists(p)
        pd.read_parquet(p)  # 可读
