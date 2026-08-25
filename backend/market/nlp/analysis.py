# -*- coding: utf-8 -*-
"""技能图谱分析（REQ-NLP-03/04/05）：
- 高频技能 Top30（统计口径 = 命中该技能的岗位数 / 有效岗位总数，占比）
- 按城市 / 岗位类别的技能差异对比
- 中文词云（R7 中文字体）
- features.parquet 产出（skills_hit / skills_count）
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from market.config import Config
from market.nlp.skills import SkillMatcher

logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False


def top_skills(df: pd.DataFrame, matcher: SkillMatcher, top_k: int = 30) -> pd.DataFrame:
    """技能 TopK：命中岗位数 / 有效岗位总数（占比口径，REQ-NLP-03）。"""
    n = len(df)
    if n == 0:
        return pd.DataFrame(columns=["skill", "hit_jobs", "ratio"])
    all_hits = df["skills_hit"] if "skills_hit" in df else df["job_desc"].fillna("").apply(matcher.match_skills)
    from collections import Counter

    counter: Counter = Counter()
    for hits in all_hits:
        counter.update(hits)
    top = counter.most_common(top_k)
    return pd.DataFrame([
        {"skill": s, "hit_jobs": c, "ratio": round(c / n, 4)} for s, c in top
    ])


def plot_top_skills(top_df: pd.DataFrame, cfg: Config, top_k: int = 30) -> str:
    """技能排名条形图（REQ-NLP-03）。"""
    fig, ax = plt.subplots(figsize=(10, 9))
    data = top_df.head(top_k).iloc[::-1]
    ax.barh(data["skill"], data["ratio"], color="#4C72B0")
    for i, (s, r) in enumerate(zip(data["skill"], data["ratio"])):
        ax.text(r + 0.002, i, f"{r:.1%}", va="center", fontsize=8)
    ax.set_xlabel("命中岗位占比")
    ax.set_title(f"技能需求 Top{top_k}（命中岗位数 / 有效岗位总数）")
    ax.set_xlim(0, min(1, data["ratio"].max() * 1.2))
    out = Path(cfg.raw["paths"]["charts_dir"]) / "nlp_top_skills.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def skill_diff(df: pd.DataFrame, matcher: SkillMatcher, group_col: str,
               top_n: int = 10) -> dict[str, pd.DataFrame]:
    """按 group（city / job_category）的技能占比差异对比（REQ-NLP-03）。"""
    result: dict[str, pd.DataFrame] = {}
    for g, sub in df.groupby(group_col):
        if len(sub) < 30:  # 样本过小组不参与对比
            continue
        from collections import Counter

        counter: Counter = Counter()
        hits_col = sub["skills_hit"] if "skills_hit" in sub else sub["job_desc"].fillna("").apply(matcher.match_skills)
        for hits in hits_col:
            counter.update(hits)
        n = len(sub)
        result[g] = pd.DataFrame([
            {"skill": s, "ratio": round(c / n, 4)} for s, c in counter.most_common(top_n)
        ])
    return result


def plot_skill_diff_heatmap(diff: dict[str, pd.DataFrame], cfg: Config, top_n: int = 8) -> str:
    """城市/类别 × 技能 TopN 占比热力图（差异对比图，REQ-NLP-03）。"""
    groups = list(diff.keys())
    # 取各组合计出现最多的 top_n 技能
    from collections import Counter

    skill_cnt: Counter = Counter()
    for gdf in diff.values():
        skill_cnt.update(dict(zip(gdf["skill"], gdf["ratio"])))
    top_skills_list = [s for s, _ in skill_cnt.most_common(top_n)]

    rows = []
    for g in groups:
        gmap = dict(zip(diff[g]["skill"], diff[g]["ratio"]))
        rows.append([gmap.get(s, 0.0) for s in top_skills_list])
    mat = pd.DataFrame(rows, index=groups, columns=top_skills_list)

    fig, ax = plt.subplots(figsize=(max(10, top_n * 1.4), max(5, len(groups) * 0.7)))
    im = ax.imshow(mat.values, cmap="YlGnBu", aspect="auto")
    ax.set_xticks(range(len(top_skills_list)))
    ax.set_xticklabels(top_skills_list, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(groups)))
    ax.set_yticklabels(groups, fontsize=8)
    for i in range(len(groups)):
        for j in range(len(top_skills_list)):
            v = mat.values[i, j]
            if v > 0:
                ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax)
    ax.set_title("技能需求占比差异（城市 / 岗位类别）")

    out = Path(cfg.raw["paths"]["charts_dir"]) / "nlp_skill_diff.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def plot_wordcloud(df: pd.DataFrame, matcher: SkillMatcher, cfg: Config) -> str:
    """技能词云（REQ-NLP-04，R7 中文字体）。"""
    from collections import Counter

    counter: Counter = Counter()
    hits_col = df["skills_hit"] if "skills_hit" in df else df["job_desc"].fillna("").apply(matcher.match_skills)
    for hits in hits_col:
        counter.update(hits)

    from wordcloud import WordCloud

    font_path = "C:/Windows/Fonts/simhei.ttf"
    wc = WordCloud(font_path=font_path, width=900, height=600,
                   background_color="white", max_words=120,
                   collocations=False).generate_from_frequencies(counter)
    out = Path(cfg.raw["paths"]["charts_dir"]) / "nlp_wordcloud.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    wc.to_file(str(out))
    return str(out)


def save_features(df: pd.DataFrame, cfg: Config) -> str:
    """产出 features.parquet（REQ-NLP-05，中间产物不入 jobs 表）。"""
    out = Path(cfg.raw["paths"]["features_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    logger.info("features.parquet 已产出: %s", out)
    return str(out)
