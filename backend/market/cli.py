# -*- coding: utf-8 -*-
"""JobPulse 命令行入口（需求 7.3）：crawl / etl / analyze / nlp / model / viz / report / import-backup / check-env / init-db / all。

用法（合并后在 backend/ 目录下执行）：
  python -m market.cli check-env            环境检查
  python -m market.cli init-db              建库（market_jobs + market_job_snapshots）
  python -m market.cli crawl --source backup   采集（backup 兜底数据集导入）
  python -m market.cli etl                  数据质量报告
  python -m market.cli analyze              EDA 图表 + 洞察
  python -m market.cli nlp                  技能图谱（Top30/差异/词云/features）
  python -m market.cli model                薪资预测建模（R²/MAE/RMSE/特征重要性）
  python -m market.cli viz                  生成 ECharts 看板
  python -m market.cli report               生成分析报告 report.md
  python -m market.cli all                  一键全流程
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from market.config import load_config
from market.logging_config import setup_logging

logger = logging.getLogger("cli")


def _setup() -> tuple[argparse.Namespace, object]:
    parser = argparse.ArgumentParser(prog="jobpulse", description="JobPulse 招聘情报站")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check-env", help="环境检查")
    sub.add_parser("init-db", help="建库")
    p_crawl = sub.add_parser("crawl", help="采集（--source backup/job51/iguopin/nowcoder）")
    p_crawl.add_argument("--source", default="backup",
                         choices=["backup", "job51", "iguopin", "nowcoder"])
    p_crawl.add_argument("--date", default=None, help="批次时间 YYYY-MM-DD HH:MM:SS（测试用）")
    sub.add_parser("etl", help="ETL 数据质量报告")
    sub.add_parser("analyze", help="EDA 探索分析")
    sub.add_parser("nlp", help="技能图谱")
    sub.add_parser("model", help="薪资预测建模")
    sub.add_parser("viz", help="生成看板")
    sub.add_parser("report", help="分析报告")
    sub.add_parser("all", help="一键全流程")

    args = parser.parse_args()
    cfg = load_config()
    return args, cfg


# ---------------------------------------------------------------- 各命令

def cmd_check_env(cfg) -> int:
    import importlib
    import platform

    from market.storage.session import get_engine

    print("=" * 50)
    print("JobPulse 环境检查")
    print("=" * 50)
    print(f"Python: {platform.python_version()} ({platform.system()})")

    required = [
        ("pandas", "pandas"), ("numpy", "numpy"), ("sqlalchemy", "SQLAlchemy"),
        ("pymysql", "PyMySQL"), ("jieba", "jieba"), ("matplotlib", "matplotlib"),
        ("xgboost", "xgboost"), ("sklearn", "scikit-learn"),
        ("wordcloud", "wordcloud"), ("pytest", "pytest"),
        ("openpyxl", "openpyxl"), ("pyarrow", "pyarrow"),
    ]
    missing = []
    for mod, disp in required:
        try:
            importlib.import_module(mod)
            print(f"  ✔ {disp}")
        except ImportError:
            missing.append(disp)
            print(f"  ✘ {disp} 缺失")
    if missing:
        print(f"缺失依赖: {missing}，请执行 pip install -r requirements.txt")
        return 1

    # DB 连通性
    try:
        engine = get_engine(cfg)
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        print(f"  ✔ 数据库连接: {cfg.sqlalchemy_url().split('@')[-1]}")
    except Exception as e:
        print(f"  ✘ 数据库连接失败: {e}（可切换 config 中 driver=sqlite 开发兜底）")
        return 1

    # 数据集
    ds = cfg.raw["crawler"]["backup_dataset"]
    print(f"  {'✔' if Path(ds).exists() else '✘'} 兜底数据集: {ds}")
    print("=" * 50)
    return 0


def cmd_init_db(cfg) -> int:
    from market.storage import init_db

    init_db(cfg)
    print("建库完成：market_jobs / market_job_snapshots（幂等补建，生产环境由宿主迁移 002 建表）")
    return 0


def cmd_crawl(cfg, source: str, date_str: str | None) -> int:
    from datetime import datetime

    from market.crawler.pipeline import run_crawl

    crawl_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S") if date_str else None
    result = run_crawl(cfg, source=source, crawl_date=crawl_date)
    print(f"采集完成: source={result.source} 写入 jobs {result.jobs_total} 条"
          f"（有效 {result.valid_total}），快照新增 {result.snapshots_added} 条")
    for w in result.warnings:
        logger.error("⚠ %s", w)
        print(f"⚠ {w}")
    return 0


def cmd_etl(cfg) -> int:
    from market.etl.quality_report import generate_quality_report

    p = generate_quality_report(cfg)
    print(f"数据质量报告: {p}")
    return 0


def cmd_analyze(cfg) -> int:
    from market.analysis.eda import run_eda, save_eda_json

    result = run_eda(cfg)
    save_eda_json(result, cfg)
    print(f"EDA 完成: {len(result['charts'])} 张图，{len(result['insights'])} 条洞察")
    for i in result["insights"]:
        print(f"  - {i['title']}")
    return 0


def cmd_nlp(cfg) -> int:
    from market.nlp import (SkillMatcher, plot_skill_diff_heatmap, plot_top_skills,
                         plot_wordcloud, save_features, skill_diff, top_skills)
    from market.storage import fetch_jobs_for_analysis

    df = fetch_jobs_for_analysis(cfg, valid_only=True)
    matcher = SkillMatcher()
    df = matcher.compute_features(df)
    top = top_skills(df, matcher, 30)
    print("技能 Top10（命中岗位占比）:")
    for _, r in top.head(10).iterrows():
        print(f"  {r['skill']:<10} {r['ratio']:.1%}")
    print(f"技能词表: {matcher.word_count} 个")
    plot_top_skills(top, cfg)
    plot_skill_diff_heatmap(skill_diff(df, matcher, "job_category", 8), cfg)
    plot_wordcloud(df, matcher, cfg)
    save_features(df, cfg)
    print("NLP 完成：Top30/差异图/词云/features.parquet 已产出")
    return 0


def cmd_model(cfg) -> int:
    from market.model.train import run_model, save_model_eval

    result = run_model(cfg)
    save_model_eval(result, cfg)
    print(f"建模完成: R²={result['xgb']['r2']} MAE={result['xgb']['mae']} "
          f"RMSE={result['xgb']['rmse']}（测试集 n={result['n_test']}）")
    print(f"验收: R²≥0.50 {'✅ 达标' if result['acceptance']['r2_ge_0.5'] else '❌ 未达标'}")
    print("特征重要性 Top5:", ", ".join(f"{n}({v:.3f})" for n, v in result["feature_importance"]["top10"][:5]))
    return 0


def cmd_viz(cfg) -> int:
    from market.viz import generate_dashboard

    p = generate_dashboard(cfg)
    print(f"看板已生成: {p}（双击打开）")
    return 0


def cmd_report(cfg) -> int:
    from market.report import generate_report

    p = generate_report(cfg)
    print(f"分析报告: {p}")
    return 0


def cmd_all(cfg) -> int:
    """一键全流程（AC-1）：init-db → crawl → etl → analyze → nlp → model → viz → report。"""
    steps = [
        ("init-db", lambda: cmd_init_db(cfg)),
        ("crawl", lambda: cmd_crawl(cfg, "backup", None)),
        ("etl", lambda: cmd_etl(cfg)),
        ("analyze", lambda: cmd_analyze(cfg)),
        ("nlp", lambda: cmd_nlp(cfg)),
        ("model", lambda: cmd_model(cfg)),
        ("viz", lambda: cmd_viz(cfg)),
        ("report", lambda: cmd_report(cfg)),
    ]
    failed = []
    for name, fn in steps:
        print(f"\n========== [{name}] ==========")
        try:
            rc = fn()
            if rc:
                failed.append(name)
        except Exception as e:
            logger.exception("[%s] 失败: %s", name, e)
            print(f"❌ [{name}] 失败: {e}")
            failed.append(name)
    print("\n" + "=" * 50)
    if failed:
        print(f"全流程完成（有失败步骤）: {failed}")
        return 1
    print("全流程完成 ✅（NFR-01：单模块失败不阻断主流程）")
    return 0


def main() -> int:
    # Windows 控制台/管道默认 GBK，R² 等 Unicode 字符会导致 print 抛
    # UnicodeEncodeError；统一重配置为 UTF-8（errors=replace 兜底）。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args, cfg = _setup()
    setup_logging(cfg.raw["paths"]["logs_dir"])
    os.environ.setdefault("DB_PASSWORD", cfg.database().get("password", ""))

    handlers = {
        "check-env": cmd_check_env,
        "init-db": cmd_init_db,
        "crawl": lambda c: cmd_crawl(c, args.source, args.date),
        "etl": cmd_etl,
        "analyze": cmd_analyze,
        "nlp": cmd_nlp,
        "model": cmd_model,
        "viz": cmd_viz,
        "report": cmd_report,
        "all": cmd_all,
    }
    return handlers[args.cmd](cfg)


if __name__ == "__main__":
    sys.exit(main())
