# -*- coding: utf-8 -*-
"""JobPulse 一键链路入口（AC-1，合并后版本）：
check-env → 建库 → 采集 → 分析 → 出报告。

用法：python run_market.py [--skip-crawl] [--source backup]
（需在 backend/ 目录下执行，产物落 market/output）
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def run(cmd: list[str]) -> int:
    print("\n" + "=" * 60)
    print(">>> " + " ".join(cmd))
    print("=" * 60)
    return subprocess.call(cmd, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="JobPulse 一键链路")
    parser.add_argument("--skip-crawl", action="store_true", help="跳过采集（复用已有数据）")
    parser.add_argument("--source", default="backup", choices=["backup", "job51"])
    args = parser.parse_args()

    py = os.path.join(ROOT, ".venv", "Scripts", "python.exe") if os.path.exists(
        os.path.join(ROOT, ".venv")) else sys.executable
    # 合并后 CLI 以模块方式运行：python -m market.cli <cmd>
    cli = [py, "-m", "market.cli"]

    steps = ["check-env", "init-db"]
    if not args.skip_crawl:
        steps.append(f"crawl --source {args.source}")
    steps += ["etl", "analyze", "nlp", "model", "viz", "report"]

    failed = []
    for step in steps:
        rc = run(cli + step.split())
        if rc != 0:
            failed.append(step)
    print("\n" + "=" * 60)
    if failed:
        print(f"❌ 一键链路完成（失败步骤: {failed}，可单独重跑）")
        return 1
    print("✅ 一键链路全部完成！产物：")
    print("   - 看板: market/output/dashboard/jobpulse_dashboard.html（双击打开）")
    print("   - 报告: market/output/reports/report.md")
    print("   - 模型评估: market/output/reports/model_evaluation.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
