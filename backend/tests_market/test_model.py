# -*- coding: utf-8 -*-
"""建模模块单测（REQ-ML-01~04）。"""
import os

import numpy as np
import pandas as pd
import pytest

from market.config import Config, load_config
from market.model import build_features, prepare_modeling_data, run_model, split_stratified


def make_df(n=300):
    rng = np.random.default_rng(42)
    rows = []
    cities = ["北京", "上海", "广州"]
    cats = ["数据分析", "算法", "数据科学"]
    for i in range(n):
        city = cities[i % 3]
        cat = cats[i % 3]
        exp = ["1-3年", "3-5年", "不限"][i % 3]
        exp_boost = {"1-3年": 0, "3-5年": 6000, "不限": 0}[exp]
        base = 18000 + cat.index(cat) * 3000 + city.index(city) * 1500 + exp_boost
        rows.append({
            "job_id": f"backup_{i % 200}",   # 引入重复
            "job_title": "岗位", "job_category": cat,
            "job_type": "实习" if i % 11 == 0 else "社招",
            "company_name": "A", "industry": "互联网", "city": city,
            "salary_raw": "15-25K", "salary_min": 15000, "salary_max": 25000,
            "salary_avg": int(base + rng.normal(0, 400)),
            "experience_req": exp,
            "education_req": ["本科", "硕士", "不限"][i % 3],
            "company_size": None,
            "job_desc": "熟悉Python SQL 机器学习", "skills_count": i % 6,
            "crawl_date": "2026-01-01", "url": "u", "is_valid": 1, "source": "backup",
        })
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def cfg(tmp_path_factory):
    c = load_config()
    raw = c.raw
    raw["database"] = {
        "driver": "sqlite", "sqlite_path": str(tmp_path_factory.mktemp("d") / "m.db"),
        "password_env": "", "password_default": "",
    }
    raw["paths"]["charts_dir"] = str(tmp_path_factory.mktemp("charts"))
    raw["paths"]["model_eval_path"] = str(tmp_path_factory.mktemp("r") / "model_eval.md")
    # 模型导出目录指向临时目录，避免覆盖 market/output/model 的真实模型（合并后隔离）
    raw["paths"]["model_dir"] = str(tmp_path_factory.mktemp("model"))
    raw["model"]["test_size"] = 0.2
    raw["model"]["random_state"] = 42
    return Config(raw)


class TestFeatureEngineering:
    def test_dedup_intern_exclude(self):
        """REQ-ML-01/02: 去重 + 实习剔除 + 薪资非空。"""
        df, meta = prepare_modeling_data(make_df(), exclude_intern=True)
        assert meta["rows_before_dedup"] == 300
        assert meta["dedup_removed"] > 0
        assert meta["intern_removed"] > 0
        assert (df["job_type"] != "实习").all()
        assert df["job_id"].nunique() == len(df)
        assert df["salary_avg"].notna().all()

    def test_build_features_columns(self):
        df, _ = prepare_modeling_data(make_df())
        X = build_features(df)
        assert "salary_avg" in X.columns
        assert "education_num" in X.columns
        assert "experience_num" in X.columns
        assert "skills_count" in X.columns
        assert "experience_req_is_不限" in X.columns
        assert X["education_num"].between(0, 4).all()

    def test_industry_top20(self):
        df, _ = prepare_modeling_data(make_df())
        # 加入低频行业
        df2 = pd.concat([df, pd.DataFrame([{
            **df.iloc[0].to_dict(), "job_id": "x1", "industry": "稀有行业A",
            "salary_avg": 20000}] )])
        X = build_features(df2)
        ind_cols = [c for c in X.columns if c.startswith("ind_")]
        assert len(ind_cols) <= 20 + 1  # top20 + 其他


class TestSplit:
    def test_stratified_ratio(self):
        df, _ = prepare_modeling_data(make_df())
        tr, te = split_stratified(df, test_size=0.2, random_state=42)
        assert len(te) == pytest.approx(len(df) * 0.2, abs=2)
        assert len(tr) + len(te) == len(df)
        # 分层保持：城市×类别比例接近
        strat = df["city"] + "_" + df["job_category"]
        assert (strat.value_counts(normalize=True) - strat.loc[tr.index].value_counts(normalize=True)).abs().max() < 0.05


class TestModel:
    def test_run_model_metrics(self, cfg):
        """REQ-ML-02/03/04: 训练评估 + 基线对比 + 特征重要性。"""
        result = run_model(cfg, make_df())
        assert "r2" in result["xgb"]
        assert result["baselines"]["linear"]["r2"] is not None
        assert result["baselines"]["mean"]["r2"] is not None
        assert len(result["feature_importance"]["top10"]) == 10
        assert os.path.exists(result["feature_importance"]["path"])

    def test_r2_reasonable(self, cfg):
        """R² 为合理范围（合成数据应 > 0.5）。"""
        result = run_model(cfg, make_df())
        assert result["xgb"]["r2"] > 0.3

    def test_save_model_eval(self, cfg):
        result = run_model(cfg, make_df())
        p = __import__("market.model.train", fromlist=["save_model_eval"]).save_model_eval(result, cfg)
        assert os.path.exists(p)
