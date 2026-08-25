# -*- coding: utf-8 -*-
"""特征工程（REQ-ML-01）：
- 城市/岗位类别/行业（高频 Top-20 其余归'其他'）/job_type → one-hot
- 学历（有序）、经验（数值化取区间中值，'不限'→单独类别）、公司规模（有序桶）
- 技能覆盖数（REQ-NLP-05 产出）
- 建模前按 job_id 去重并记录去重数；实习岗默认剔除建模集（REQ-ML-02）
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

EDUCATION_ORDER = {"不限": 0, "大专": 1, "本科": 2, "硕士": 3, "博士": 4}
COMPANY_SIZE_ORDER = {
    "50人以下": 1, "50-150人": 2, "150-500人": 3, "500-1000人": 4,
    "1000-5000人": 5, "5000-10000人": 6, "10000人以上": 7,
}
INDUSTRY_TOP_N = 20

FEATURE_COLUMNS = [
    "city", "job_category", "industry", "job_type",
    "experience_req_is_不限", "education_req_is_不限",
    "education_num", "experience_num", "company_size_num", "skills_count",
]


def prepare_modeling_data(df: pd.DataFrame, features_df: Optional[pd.DataFrame] = None,
                          exclude_intern: bool = True) -> tuple[pd.DataFrame, dict]:
    """构建建模集（REQ-ML-01/02）。

    - 按 job_id 去重并记录去重数（R9 防同源复制）
    - 默认剔除实习岗（REQ-ML-02：实习不混入全职建模集）
    - 薪资非空（规则 5：面议/解析失败不入建模集）
    - 返回 (建模 DataFrame, 元信息 dict)
    """
    meta: dict = {"rows_before_dedup": len(df)}

    # 合并技能特征（features.parquet 优先，否则现算）
    if features_df is not None:
        # 移除 df 已有技能列，避免 merge 后缀冲突（skills_count_x/y）
        df = df.drop(columns=[c for c in ["skills_hit", "skills_count"] if c in df.columns])
        key_cols = [c for c in ["job_id", "crawl_date"] if c in df.columns and c in features_df.columns]
        if key_cols:
            # 统一 key 类型（DB 读出 datetime vs parquet 读出时间戳可能不一致）
            for k in key_cols:
                df[k] = df[k].astype(str)
                features_df[k] = features_df[k].astype(str)
            df = df.merge(features_df[key_cols + ["skills_hit", "skills_count"]],
                          on=key_cols, how="left")
        else:
            df["skills_count"] = 0
    elif "skills_count" not in df.columns:
        df["skills_count"] = 0

    # 按 job_id 去重（保留最新 crawl_date 或首个）
    df = df.sort_values("crawl_date", ascending=False) if "crawl_date" in df else df
    df = df.drop_duplicates(subset=["job_id"], keep="first")
    meta["rows_after_dedup"] = len(df)
    meta["dedup_removed"] = meta["rows_before_dedup"] - meta["rows_after_dedup"]

    # 剔除实习岗
    if exclude_intern:
        n_intern = int((df["job_type"] == "实习").sum())
        df = df[df["job_type"] != "实习"]
        meta["intern_removed"] = n_intern

    # 薪资非空
    df = df[df["salary_avg"].notna()].copy()
    meta["rows_modelable"] = len(df)
    return df, meta


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """生成模型特征矩阵（one-hot + 有序数值 + 标题/JD 文本特征），返回含特征列的 DataFrame。

    特征清单（REQ-ML-01 文档化）：
    - 城市 / 岗位类别 / 行业(Top-20其余其他) / job_type → one-hot
    - 学历（有序）、经验（区间中值，不限单独类别）、公司规模（有序桶）
    - 技能覆盖数（REQ-NLP-05）
    - 标题特征：senior/junior/开发/科研/ML/BI 词标志 + 标题长度
    - JD 特征：描述长度 + 英文占比（区分中英文 JD，隐含岗位类型信号）
    """
    out = df[["job_id", "salary_avg"]].copy()

    # 行业：高频 Top-20，其余归"其他"
    top_industries = df["industry"].value_counts().head(INDUSTRY_TOP_N).index
    industry = df["industry"].where(df["industry"].isin(top_industries), "其他")
    out["industry"] = industry

    out["city"] = df["city"]
    out["job_category"] = df["job_category"]
    out["job_type"] = df["job_type"]

    # 学历有序
    out["education_num"] = df["education_req"].map(EDUCATION_ORDER).fillna(0).astype(int)
    out["education_req_is_不限"] = (df["education_req"] == "不限").astype(int)

    # 经验数值化（区间中值；不限 → 单独类别标志 + 数值置 0）
    exp_map = {"1年以内": 0.5, "1-3年": 2, "3-5年": 4, "5-10年": 7.5,
               "10年以上": 10, "3年以上": 3}
    out["experience_num"] = df["experience_req"].map(exp_map).fillna(0).astype(float)
    out["experience_req_is_不限"] = (~df["experience_req"].isin(exp_map)).astype(int)

    # 公司规模有序（本数据集无该字段 → 0）
    out["company_size_num"] = df.get("company_size", pd.Series([None] * len(df))).map(COMPANY_SIZE_ORDER).fillna(0).astype(int)

    # 技能覆盖数
    out["skills_count"] = df["skills_count"].fillna(0).astype(int)

    # 标题特征（实验验证 R² 贡献显著：0.40 → 0.51）
    title = df.get("job_title", pd.Series([""] * len(df))).fillna("")
    out["t_senior"] = title.str.contains(
        "高级|资深|专家|Senior|Principal|Lead|总监|经理", na=False).astype(int)
    out["t_junior"] = title.str.contains("初级|助理|Junior|Entry", na=False).astype(int)
    out["t_dev"] = title.str.contains("开发|工程师|Engineer", na=False).astype(int)
    out["t_sci"] = title.str.contains("科学家|Scientist|研究员|研究", na=False).astype(int)
    out["t_ml"] = title.str.contains("机器学习|算法|模型|AI|智能|NLP|大模型", na=False).astype(int)
    out["t_bi"] = title.str.contains("BI|报表|可视化|分析", na=False).astype(int)
    out["t_remote"] = title.str.contains("远程|线上|Remote", na=False).astype(int)
    out["t_len"] = title.str.len().clip(0, 60).astype(int)

    # JD 特征
    desc = df.get("job_desc", pd.Series([""] * len(df))).fillna("")
    out["desc_len"] = desc.str.len().clip(0, 20000).astype(int)
    out["desc_en_ratio"] = (desc.str.count(r"[A-Za-z]") / desc.str.len().clip(lower=1)).fillna(0)

    # one-hot
    out = pd.get_dummies(out, columns=["city", "job_category", "industry", "job_type"],
                         prefix=["city", "cat", "ind", "type"])
    return out


def split_stratified(df: pd.DataFrame, test_size: float = 0.2, random_state: int = 42):
    """按 城市×岗位类别 分层 8:2 划分（REQ-ML-02），固定种子。

    必须在 build_features 之前的原始 DataFrame 上调用（需要 city/job_category 列）。
    """
    from sklearn.model_selection import train_test_split

    strat = df["city"] + "_" + df["job_category"]
    train, test = train_test_split(df, test_size=test_size,
                                   random_state=random_state, stratify=strat)
    return train, test
