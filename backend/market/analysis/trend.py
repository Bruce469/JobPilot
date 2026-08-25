# -*- coding: utf-8 -*-
"""时间趋势分析（REQ-EDA-04，P2 加分项）：
基于 market_job_snapshots 表按 crawl_date 统计岗位量/薪资变化。
需 ≥2 个采集批次；批次不足时声明样本不足（AC-11 降级判定）。
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from market.config import Config
from market.storage.session import session_scope

logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False


def load_snapshot_series(cfg: Config) -> pd.DataFrame:
    """从 job_snapshots 读取 (crawl_date, 岗位量, 薪资中位数) 时序。"""
    from market.storage.models import JobSnapshot
    from sqlalchemy import select

    with session_scope(cfg) as s:
        rows = [
            (sn.crawl_date, sn.salary_avg, sn.is_valid)
            for sn in s.scalars(select(JobSnapshot))
        ]
    if not rows:
        return pd.DataFrame(columns=["batch", "jobs", "salary_median"])
    df = pd.DataFrame(rows, columns=["crawl_date", "salary_avg", "is_valid"])
    # 按批次（crawl_date）聚合：有效岗位量 + 薪资中位数
    valid = df[df["is_valid"] == 1]
    grouped = valid.groupby("crawl_date")["salary_avg"].agg(
        jobs="count", salary_median="median").reset_index()
    grouped = grouped.sort_values("crawl_date")
    return grouped


def plot_trend(cfg: Config) -> str | None:
    """生成趋势图；批次 <2 时返回 None（声明样本不足）。"""
    series = load_snapshot_series(cfg)
    if len(series) < 2:
        logger.info("快照批次 %d <2，时间趋势样本不足（AC-11 降级：声明不产出）", len(series))
        return None

    fig, ax1 = plt.subplots(figsize=(10, 5))
    x = range(len(series))
    ax1.bar(x, series["jobs"], color="#4C72B0", alpha=0.7, label="有效岗位量")
    ax1.set_ylabel("有效岗位量")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(series["crawl_date"].dt.strftime("%m-%d"), rotation=15)

    ax2 = ax1.twinx()
    ax2.plot(x, series["salary_median"], color="#C44E52", marker="o", label="薪资中位数（元）")
    ax2.set_ylabel("薪资中位数（元）")
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    ax1.set_title("采集批次 × 岗位量 / 薪资中位数（基于 job_snapshots）")

    out = Path(cfg.raw["paths"]["charts_dir"]) / "trend_snapshots.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    logger.info("时间趋势图已生成: %s", out)
    return str(out)
