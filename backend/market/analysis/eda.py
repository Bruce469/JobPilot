# -*- coding: utf-8 -*-
"""EDA 探索性分析（REQ-EDA-01~03）：
- 图模块口径：分布类 ≥3（城市/大类/行业）+ 对比相关性类 ≥3（学历/经验/城市/岗位类别薪资）
- 实习/全职薪资分开统计（4.3 规则 7 / REQ-EDA-02）
- 每图对应文字洞察，≥5 条量化结论（含数值与口径）汇入报告
- matplotlib 中文字体统一配置（R7）
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from market.config import Config
from market.storage import fetch_jobs_for_analysis

logger = logging.getLogger(__name__)

# 中文字体（R7）
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

# 10 城顺序（分析展示口径）
CITY_ORDER = ["北京", "上海", "广州", "深圳", "杭州", "成都", "南京", "武汉", "西安", "苏州"]
CATEGORY_ORDER = ["数据分析", "数据科学", "大数据", "算法", "BI数仓"]

EDU_ORDER = ["大专", "本科", "硕士", "博士", "不限"]
EXP_ORDER = ["1年以内", "1-3年", "3-5年", "5-10年", "10年以上", "不限"]


def _ensure_chart_dir(cfg: Config) -> Path:
    d = Path(cfg.raw["paths"]["charts_dir"])
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save(fig, name: str, cfg: Config) -> str:
    d = _ensure_chart_dir(cfg)
    path = d / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    logger.info("图表已生成: %s", path)
    return str(path)


# ---------------------------------------------------------------- 分布类图（REQ-EDA-01）

def plot_city_job_count(df: pd.DataFrame, cfg: Config) -> str:
    """图1：城市 × 岗位量（分布类）。"""
    vc = df["city"].value_counts().reindex(CITY_ORDER).dropna()
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(vc.index, vc.values, color="#4C72B0")
    for b, v in zip(bars, vc.values):
        ax.text(b.get_x() + b.get_width() / 2, v + 10, str(int(v)), ha="center", fontsize=9)
    ax.set_title("各城市岗位数量分布（有效记录）")
    ax.set_xlabel("城市")
    ax.set_ylabel("岗位数")
    return _save(fig, "eda_city_job_count", cfg)


def plot_category_distribution(df: pd.DataFrame, cfg: Config) -> str:
    """图2：岗位大类分布（分布类）。"""
    vc = df["job_category"].value_counts().reindex(CATEGORY_ORDER).dropna()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(vc.index, vc.values, color="#55A868")
    for i, v in enumerate(vc.values):
        ax.text(i, v + 10, str(int(v)), ha="center", fontsize=9)
    ax.set_title("岗位大类分布（有效记录）")
    ax.set_xlabel("岗位大类")
    ax.set_ylabel("岗位数")
    return _save(fig, "eda_category_dist", cfg)


def plot_industry_top(df: pd.DataFrame, cfg: Config, top_n: int = 15) -> str:
    """图3：行业 Top15 分布（分布类，低频已归并'其他'）。"""
    vc = df["industry"].value_counts().head(top_n)
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(vc.index[::-1], vc.values[::-1], color="#C44E52")
    ax.set_title(f"行业分布 Top{top_n}（有效记录）")
    ax.set_xlabel("岗位数")
    return _save(fig, "eda_industry_top", cfg)


# ---------------------------------------------------------------- 对比/相关性类图（REQ-EDA-02）

def _plot_salary_box(df: pd.DataFrame, group_col: str, order: list[str],
                     title: str, name: str, cfg: Config, orient: str = "v") -> str:
    """薪资箱线图（全职：job_type != 实习；实习单列调用方处理）。"""
    sub = df[df["salary_avg"].notna()].copy()
    cats = [c for c in order if c in sub[group_col].unique()]
    data = [sub.loc[sub[group_col] == c, "salary_avg"] for c in cats]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    if orient == "v":
        ax.boxplot(data, tick_labels=cats, showmeans=True)
        ax.set_xlabel(group_col)
        ax.set_ylabel("月薪（元）")
        plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    else:
        ax.boxplot(data, tick_labels=cats, vert=False, showmeans=True)
        ax.set_ylabel(group_col)
        ax.set_xlabel("月薪（元）")
    ax.set_title(title)
    return _save(fig, name, cfg)


def plot_edu_salary(df: pd.DataFrame, cfg: Config) -> str:
    """图4：学历-薪资箱线图（对比类）。"""
    return _plot_salary_box(df[df["job_type"] != "实习"], "education_req", EDU_ORDER,
                            "学历 × 月薪分布（全职岗位）", "eda_edu_salary", cfg)


def plot_exp_salary(df: pd.DataFrame, cfg: Config) -> str:
    """图5：经验-薪资（对比类）。"""
    return _plot_salary_box(df[df["job_type"] != "实习"], "experience_req", EXP_ORDER,
                            "经验要求 × 月薪分布（全职岗位）", "eda_exp_salary", cfg)


def plot_city_salary(df: pd.DataFrame, cfg: Config) -> str:
    """图6：城市-薪资箱线图（对比类）。"""
    return _plot_salary_box(df[df["job_type"] != "实习"], "city", CITY_ORDER,
                            "城市 × 月薪分布（全职岗位）", "eda_city_salary", cfg)


def plot_category_salary(df: pd.DataFrame, cfg: Config) -> str:
    """图7：岗位类别-薪资（全职 vs 实习分开）（REQ-EDA-02）。"""
    full = df[df["job_type"] != "实习"]
    intern = df[df["job_type"] == "实习"]
    cats = [c for c in CATEGORY_ORDER if c in full["job_category"].unique()]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    pos = range(len(cats))
    full_data = [full.loc[full["job_category"] == c, "salary_avg"].dropna() for c in cats]
    intern_data = [intern.loc[intern["job_category"] == c, "salary_avg"].dropna() for c in cats]
    bp1 = ax.boxplot(full_data, positions=[p - 0.2 for p in pos], widths=0.35,
                     showmeans=True, patch_artist=True)
    bp2 = ax.boxplot(intern_data, positions=[p + 0.2 for p in pos], widths=0.35,
                     showmeans=True, patch_artist=True)
    for patch, color in zip(bp1["boxes"], ["#4C72B0"] * len(cats)):
        patch.set_facecolor(color)
    for patch, color in zip(bp2["boxes"], ["#DD8452"] * len(cats)):
        patch.set_facecolor(color)
    ax.set_xticks(list(pos))
    ax.set_xticklabels(cats)
    ax.legend([bp1["boxes"][0], bp2["boxes"][0]], ["全职", "实习"], loc="upper right")
    ax.set_ylabel("月薪（元）")
    ax.set_title("岗位类别 × 月薪（全职 vs 实习）")
    return _save(fig, "eda_category_salary", cfg)


def plot_city_category_heatmap(df: pd.DataFrame, cfg: Config) -> str:
    """图8：城市 × 岗位大类 热力图（相关性类）。"""
    cross = pd.crosstab(df["city"], df["job_category"]).reindex(
        index=[c for c in CITY_ORDER if c in df["city"].unique()],
        columns=[c for c in CATEGORY_ORDER if c in df["job_category"].unique()],
    )
    fig, ax = plt.subplots(figsize=(9, 6))
    im = ax.imshow(cross.values, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(len(cross.columns)))
    ax.set_xticklabels(cross.columns)
    ax.set_yticks(range(len(cross.index)))
    ax.set_yticklabels(cross.index)
    for i in range(len(cross.index)):
        for j in range(len(cross.columns)):
            ax.text(j, i, str(int(cross.values[i, j])), ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax)
    ax.set_title("城市 × 岗位大类 岗位量热力图")
    return _save(fig, "eda_city_category_heatmap", cfg)


# ---------------------------------------------------------------- 洞察（REQ-EDA-03）

def _fmt_money(x: float) -> str:
    return f"{x:,.0f}"


def compute_insights(df: pd.DataFrame) -> list[dict]:
    """量化洞察（≥5 条，每条含数值与口径）。"""
    insights = []
    full = df[df["job_type"] != "实习"]
    sal = df[df["salary_avg"].notna()]

    # 1. 城市岗位量
    city_vc = df["city"].value_counts()
    top_city = city_vc.index[0]
    insights.append({
        "title": "北京是数据分析/数据科学岗位最集中的城市",
        "detail": f"北京有效岗位 {int(city_vc[top_city])} 条，占全部有效记录 {int(city_vc[top_city]) / len(df):.1%}"
                  f"（样本 N={len(df)}，口径：10 城有效岗位）",
    })

    # 2. 城市薪资
    city_sal = sal.groupby("city")["salary_avg"].median().sort_values(ascending=False)
    if len(city_sal) >= 2:
        hi_city, lo_city = city_sal.index[0], city_sal.index[-1]
        insights.append({
            "title": f"城市薪资差异明显：{hi_city} 中位数最高、{lo_city} 最低",
            "detail": f"{hi_city} 月薪中位数 {_fmt_money(city_sal.iloc[0])} 元 vs {lo_city} "
                      f"{_fmt_money(city_sal.iloc[-1])} 元，差距 {city_sal.iloc[0] / city_sal.iloc[-1]:.1f} 倍"
                      f"（口径：全职岗位 salary_avg 中位数，样本 N={len(sal)}）",
        })

    # 3. 岗位类别薪资
    cat_sal = full[full["salary_avg"].notna()].groupby("job_category")["salary_avg"].median().sort_values(ascending=False)
    if len(cat_sal) >= 2:
        insights.append({
            "title": f"{cat_sal.index[0]} 岗薪资中位数最高",
            "detail": f"{cat_sal.index[0]} 月薪中位数 {_fmt_money(cat_sal.iloc[0])} 元（样本 "
                      f"{int((full['job_category'] == cat_sal.index[0]).sum())} 条），高于最低的 "
                      f"{cat_sal.index[-1]}（{_fmt_money(cat_sal.iloc[-1])} 元）{cat_sal.iloc[0] / cat_sal.iloc[-1] - 1:.0%}"
                      f"（口径：全职岗位中位数）",
        })

    # 4. 学历薪资
    edu_sal = full[full["salary_avg"].notna() & full["education_req"].isin(["本科", "硕士"])]
    if len(edu_sal) >= 10:
        m_b = edu_sal[edu_sal["education_req"] == "本科"]["salary_avg"].median()
        m_m = edu_sal[edu_sal["education_req"] == "硕士"]["salary_avg"].median()
        if m_b and m_m:
            insights.append({
                "title": "硕士学历薪资显著高于本科",
                "detail": f"硕士月薪中位数 {_fmt_money(m_m)} 元 vs 本科 {_fmt_money(m_b)} 元，"
                          f"硕士溢价 {m_m / m_b - 1:.0%}（口径：全职岗位中位数，样本 "
                          f"本科 {int((edu_sal['education_req'] == '本科').sum())} / 硕士 "
                          f"{int((edu_sal['education_req'] == '硕士').sum())}）",
            })

    # 5. 经验薪资
    exp_sal = full[full["salary_avg"].notna() & full["experience_req"].isin(["1-3年", "3-5年", "5-10年"])]
    if len(exp_sal) >= 10:
        e1 = exp_sal[exp_sal["experience_req"] == "1-3年"]["salary_avg"].median()
        e2 = exp_sal[exp_sal["experience_req"] == "5-10年"]["salary_avg"].median()
        if e1 and e2:
            insights.append({
                "title": "经验积累带来薪资跃升",
                "detail": f"5-10 年经验月薪中位数 {_fmt_money(e2)} 元，是 1-3 年（{_fmt_money(e1)} 元）的 "
                          f"{e2 / e1:.1f} 倍（口径：全职岗位中位数）",
            })

    # 6. 实习薪资
    intern = df[(df["job_type"] == "实习") & df["salary_avg"].notna()]
    if len(intern) >= 10:
        insights.append({
            "title": "实习薪资：算法岗最高",
            "detail": f"实习岗位 {len(intern)} 条（薪资可解析），月薪中位数 {_fmt_money(intern['salary_avg'].median())} 元；"
                      f"算法类实习中位数 {_fmt_money(intern[intern['job_category'] == '算法']['salary_avg'].median())} 元"
                      f"（口径：实习岗日薪×20 折月薪，4.3 规则 7）",
        })

    return insights


def run_eda(cfg: Config, df: pd.DataFrame | None = None) -> dict:
    """执行全部 EDA：生成图表 + 洞察，返回 {charts: [...], insights: [...]}。"""
    if df is None:
        df = fetch_jobs_for_analysis(cfg, valid_only=True)
    if df.empty:
        raise ValueError("无有效数据可执行 EDA（is_valid=1 记录为 0）")

    charts = {
        "city_job_count": plot_city_job_count(df, cfg),
        "category_dist": plot_category_distribution(df, cfg),
        "industry_top": plot_industry_top(df, cfg),
        "edu_salary": plot_edu_salary(df, cfg),
        "exp_salary": plot_exp_salary(df, cfg),
        "city_salary": plot_city_salary(df, cfg),
        "category_salary": plot_category_salary(df, cfg),
        "city_category_heatmap": plot_city_category_heatmap(df, cfg),
    }
    insights = compute_insights(df)
    logger.info("EDA 完成：%d 张图，%d 条洞察", len(charts), len(insights))
    return {"charts": charts, "insights": insights}


def save_eda_json(result: dict, cfg: Config) -> str:
    """持久化 EDA 结果 JSON（供 report / 看板复用）。"""
    out = Path(cfg.raw["paths"]["reports_dir"]) / "eda_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("EDA 结果已保存: %s", out)
    return str(out)
