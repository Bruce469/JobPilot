# -*- coding: utf-8 -*-
"""分析报告生成（REQ-DEL-02）：
汇总 EDA 洞察、图表引用、技能图谱、模型评估、数据质量到 output/reports/report.md。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from market.config import Config
from market.storage import count_jobs, count_snapshots

logger = logging.getLogger(__name__)


def generate_report(cfg: Config, eda_result: dict | None = None,
                    model_result: dict | None = None,
                    dq_md: str | None = None) -> str:
    """生成 report.md；EDA/模型结果可复用已保存的 JSON，否则实时计算。"""
    reports_dir = Path(cfg.raw["paths"]["reports_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)

    # EDA 结果（优先已存 JSON）
    if eda_result is None:
        eda_json = reports_dir / "eda_result.json"
        if eda_json.exists():
            eda_result = json.loads(eda_json.read_text(encoding="utf-8"))
        else:
            from market.analysis.eda import run_eda, save_eda_json

            eda_result = run_eda(cfg)
            save_eda_json(eda_result, cfg)
    insights = eda_result.get("insights", [])
    charts = eda_result.get("charts", {})

    # 模型结果（优先已存，否则重算）
    if model_result is None:
        model_result = _load_model_result(cfg)

    valid = count_jobs(cfg, valid_only=True)
    total = count_jobs(cfg, valid_only=False)
    snaps = count_snapshots(cfg)

    lines = [
        "# JobPulse 招聘情报站 — 分析报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 数据量：jobs 总 {total} 条 / 有效 {valid} 条 / 快照 {snaps} 条",
        f"- 数据源：GitHub 开源数据集（Rayair019/Job-posting-data，2025 中国平台岗位，10,114 条）",
        "",
        "## 1. 核心结论（可写入简历）",
        "",
    ]
    for i, ins in enumerate(insights, 1):
        lines.append(f"### 1.{i} {ins['title']}")
        lines.append("")
        lines.append(f"{ins['detail']}")
        lines.append("")

    lines += ["## 2. 图表", ""]
    chart_names = {
        "city_job_count": "城市岗位量分布", "category_dist": "岗位大类分布",
        "industry_top": "行业 Top15", "edu_salary": "学历×薪资",
        "exp_salary": "经验×薪资", "city_salary": "城市×薪资",
        "category_salary": "岗位类别×薪资（全职 vs 实习）",
        "city_category_heatmap": "城市×大类热力图",
    }
    for key, title in chart_names.items():
        if key in charts:
            lines.append(f"- [{title}]({charts[key]})")

    lines += ["", "## 3. 技能图谱", ""]
    lines += [
        "- 技能词表：`config/skill_words.json`（89 个核心技能词）",
        "- 高频技能 Top30 统计口径：命中该技能的岗位数 / 有效岗位总数",
        "- 图表：`output/charts/nlp_top_skills.png`（Top30 排名）、`output/charts/nlp_skill_diff.png`（差异对比）、`output/charts/nlp_wordcloud.png`（词云）",
        "- 特征产物：`output/analysis/features.parquet`（skills_hit / skills_count，REQ-NLP-05）",
        "",
        "## 4. 薪资预测模型",
        "",
    ]
    if model_result:
        xgb = model_result.get("xgb", {})
        meta = model_result.get("meta", {})
        acc = model_result.get("acceptance", {})
        lines += [
            f"- 模型：XGBoost 回归（log 目标变换），预测 salary_avg",
            f"- 建模集：总 {meta.get('rows_before_dedup', '-')} 条 → 去重后 {meta.get('rows_after_dedup', '-')}"
            f"（剔除 {meta.get('dedup_removed', 0)} 重复）→ 剔除实习 {meta.get('intern_removed', 0)} → "
            f"可建模 {meta.get('rows_modelable', '-')} 条",
            f"- 评估（测试集）：**R² = {xgb.get('r2', '-')}**，MAE = {xgb.get('mae', '-')}，RMSE = {xgb.get('rmse', '-')}",
            f"- 验收：R² ≥ 0.50 → {'✅ 达标' if acc.get('r2_ge_0.5') else '❌ 未达标'}",
            f"- 基线对比：线性回归 R²={model_result.get('baselines', {}).get('linear', {}).get('r2', '-')}，"
            f"均值基线 R²={model_result.get('baselines', {}).get('mean', {}).get('r2', '-')}",
            f"- 特征重要性 Top10 图：`{model_result.get('feature_importance', {}).get('path', '-')}`",
            "- 实习岗默认剔除出建模集（REQ-ML-02）；目标编码无（one-hot，无泄漏风险）",
            "",
        ]
    else:
        lines += ["- 模型尚未运行（执行 `python market/cli.py model`）", ""]

    lines += ["## 5. 数据质量", ""]
    dq_path = cfg.raw["paths"]["dq_report_path"]
    lines += [f"- 数据质量报告：`{dq_path}`（缺失率/面议/异常薪资/实习单列）", ""]

    lines += ["## 6. 时间趋势说明（REQ-EDA-04）", ""]
    trend_path = None
    try:
        from market.analysis.trend import load_snapshot_series, plot_trend

        series = load_snapshot_series(cfg)
        if len(series) >= 2:
            trend_path = plot_trend(cfg)
    except Exception as e:  # 趋势分析失败不阻断报告（NFR-01）
        logger.warning("时间趋势分析失败: %s", e)
    if trend_path:
        lines += [
            f"- 快照批次数：{len(series)}（≥2，满足产出条件）。",
            f"- 趋势图：![批次趋势]({trend_path})",
            "- 当前各批次为同一数据源重复采集，岗位量与薪资保持稳定属预期；",
            "- 随增量采集批次积累（不同时间点数据源），可观察市场真实变化。",
            "",
        ]
    else:
        lines += [
            "- 快照批次数 <2：**声明：样本不足，时间趋势图暂不产出**（P2 不阻塞主线，AC-11 降级判定）。",
            "",
        ]

    lines += [
        "## 7. 限制与声明",
        "",
        "- 南京(190)/西安(143)/苏州(110) 单城样本 <200，属数据集覆盖限制（需求 4.4 弹性标准，报告中声明）。",
        "- 数据为 2025 年中国主流招聘平台公开岗位文本，分析结论为市场趋势参考（3.2）。",
        "- 数据集无明确开源许可证，仅限个人学习使用，不二次分发（README 声明）。",
        "",
    ]
    out = Path(cfg.raw["paths"]["report_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    logger.info("分析报告已生成: %s", out)
    return str(out)


def _load_model_result(cfg: Config) -> dict | None:
    """从 model_evaluation.md 无法反序列化，直接重算模型（数据量小，快）。"""
    try:
        from market.model.train import run_model

        return run_model(cfg)
    except Exception as e:  # 建模失败不阻断报告（NFR-01）
        logger.warning("模型重算失败，报告中跳过模型章节: %s", e)
        return None
