# -*- coding: utf-8 -*-
"""数据质量报告（REQ-DQ-03）：
运行产出 output/reports/data_quality_report.md，
含报告生成时间、数据量、每字段缺失率、面议比例、异常薪资占比、
未知薪资格式数、实习薪资单列统计。
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from market.config import Config
from market.storage import fetch_jobs_for_analysis

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = [
    "job_id", "job_title", "job_category", "job_type", "company_name",
    "industry", "city", "salary_raw", "experience_req", "education_req",
    "job_desc", "crawl_date", "url", "is_valid", "source",
]
NUMERIC_FIELDS = ["salary_min", "salary_max", "salary_avg"]
OPTIONAL_FIELDS = ["company_size", "tags", "post_date"]


def compute_quality_stats(df: pd.DataFrame) -> dict:
    """计算数据质量统计指标（纯函数，便于单测）。"""
    n = len(df)
    stats: dict = {
        "total": n,
        "valid": int((df["is_valid"] == 1).sum()) if "is_valid" in df else n,
        "field_missing": {},
        "mianyi_count": 0,
        "salary_null_count": 0,
        "unknown_format_count": 0,
        "salary_anomaly_count": 0,
        "intern_stats": {},
    }
    # 每字段缺失率
    for col in REQUIRED_FIELDS + NUMERIC_FIELDS + OPTIONAL_FIELDS:
        if col not in df.columns:
            stats["field_missing"][col] = 1.0
            continue
        missing = df[col].isna().sum()
        stats["field_missing"][col] = round(missing / n, 4) if n else 0.0

    # 面议比例（salary_raw 含"面议"）
    if "salary_raw" in df.columns:
        mianyi_mask = df["salary_raw"].astype(str).str.contains("面议", na=False)
        stats["mianyi_count"] = int(mianyi_mask.sum())

    # 薪资为空（非面议的解析失败）
    if "salary_avg" in df.columns:
        stats["salary_null_count"] = int(df["salary_avg"].isna().sum())

    # 异常薪资（4.3 规则 6：重新解析 salary_raw，min<1500 / max>30万 / min>max）
    if "salary_raw" in df.columns:
        from market.etl.salary import parse_salary

        anomaly = 0
        for _, row in df[["salary_raw", "job_type"]].iterrows():
            r = parse_salary(str(row["salary_raw"]) if pd.notna(row["salary_raw"]) else None,
                             str(row["job_type"]) if pd.notna(row["job_type"]) else "不限")
            if r.parse_ok and not r.is_valid:
                anomaly += 1
        stats["salary_anomaly_count"] = anomaly

    # 实习薪资单列统计（4.3 规则 7）
    if {"job_type", "salary_avg"}.issubset(df.columns):
        intern = df[df["job_type"] == "实习"]
        stats["intern_stats"] = {
            "count": len(intern),
            "salary_notna": int(intern["salary_avg"].notna().sum()),
            "mean": round(intern["salary_avg"].mean(), 1) if intern["salary_avg"].notna().any() else None,
            "median": round(intern["salary_avg"].median(), 1) if intern["salary_avg"].notna().any() else None,
        }
    return stats


def render_markdown(stats: dict, generated_at: str, source_desc: str = "") -> str:
    """将统计指标渲染为 Markdown 报告。"""
    lines = [
        "# JobPulse 数据质量报告",
        "",
        f"- 报告生成时间：{generated_at}",
        f"- 数据量：总 {stats['total']} 条（有效 {stats['valid']} 条）",
        f"- 数据来源：{source_desc}",
        "",
        "## 1. 字段缺失率",
        "",
        "| 字段 | 缺失率 |",
        "|---|---|",
    ]
    for col, rate in sorted(stats["field_missing"].items(), key=lambda x: -x[1]):
        lines.append(f"| {col} | {rate:.2%} |")

    lines += [
        "",
        "## 2. 薪资质量",
        "",
        f"- 面议数量：{stats['mianyi_count']}（占 {stats['mianyi_count'] / stats['total']:.2%}）" if stats["total"] else "- 面议数量：0",
        f"- 薪资为空（解析失败/面议/缺失）：{stats['salary_null_count']}",
        f"- 异常薪资（4.3 规则 6：下限<1500/上限>30万/min>max）：{stats['salary_anomaly_count']}",
        "",
        "## 3. 实习薪资单列统计（4.3 规则 7）",
        "",
        f"- 实习岗位数：{stats['intern_stats'].get('count', 0)}",
        f"- 其中薪资可解析数：{stats['intern_stats'].get('salary_notna', 0)}",
        f"- 实习月薪均值：{stats['intern_stats'].get('mean')} 元",
        f"- 实习月薪中位数：{stats['intern_stats'].get('median')} 元",
        "",
        "## 4. 说明",
        "",
        "- 统计口径：有效记录以 `is_valid=1` 为准（REQ-SCHED-03）。",
        "- 面议/薪资解析失败记录保留但不进入建模集（4.3 规则 5）。",
        "- 异常薪资（月薪上限 >30 万 / 下限 <1500 / min>max）标记 is_valid=0（4.3 规则 6）。",
        "- 实习岗按日薪 ×20 折月薪（4.3 规则 7），不混入全职建模集（REQ-ML-02）。",
        "",
    ]
    return "\n".join(lines)


def generate_quality_report(cfg: Config, df: pd.DataFrame | None = None,
                            output_path: str | Path | None = None) -> str:
    """生成数据质量报告文件，返回文件路径。"""
    if df is None:
        df = fetch_jobs_for_analysis(cfg, valid_only=False)
    if df.empty:
        logger.warning("无数据可生成质量报告")
    stats = compute_quality_stats(df)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    source_desc = "GitHub 开源数据集（Rayair019/Job-posting-data，2025 中国平台岗位）"
    md = render_markdown(stats, generated_at, source_desc)

    out = Path(output_path) if output_path else Path(cfg.raw["paths"]["dq_report_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    logger.info("数据质量报告已生成: %s", out)
    return str(out)
