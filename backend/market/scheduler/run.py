# -*- coding: utf-8 -*-
"""增量调度（REQ-SCHED-01）：
- 增量采集命令可重复执行（幂等）
- APScheduler 定时（可选；默认提供手动执行入口）

用法：
  python -m market.scheduler.run --once                # 手动执行一次增量
  python -m market.scheduler.run --interval-hours 24   # 每 24 小时定时
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from market.config import load_config
from market.crawler.pipeline import run_crawl
from market.logging_config import setup_logging
from market.storage import count_jobs, count_snapshots

logger = logging.getLogger("scheduler")


def incremental_crawl(cfg, source: str = "backup") -> dict:
    """执行一次增量采集批次（REQ-SCHED-01）：记录新增/跳过/失效数量。

    backup 源为本地数据集导入：幂等写入 jobs（不增行）+ 快照追加新批次。
    失效标记（REQ-SCHED-03）由数据集内 is_valid 逻辑处理（城市白名单/薪资异常）。
    """
    before_jobs = count_jobs(cfg, valid_only=False)
    before_snaps = count_snapshots(cfg)

    result = run_crawl(cfg, source=source)

    after_jobs = count_jobs(cfg, valid_only=False)
    after_snaps = count_snapshots(cfg)

    stats = {
        "batch_time": result.crawl_date.isoformat(),
        "jobs_before": before_jobs, "jobs_after": after_jobs,
        "jobs_added": after_jobs - before_jobs,   # 0 = 幂等（不增行）
        "snapshots_before": before_snaps, "snapshots_after": after_snaps,
        "snapshots_added": after_snaps - before_snaps,
        "valid_total": result.valid_total,
        "warnings": result.warnings,
    }
    logger.info("增量完成: %s", stats)
    print(f"增量采集批次 {stats['batch_time']}: "
          f"jobs {before_jobs}→{after_jobs}（新增 {stats['jobs_added']}）| "
          f"快照 {before_snaps}→{after_snaps}（新增 {stats['snapshots_added']}）| "
          f"有效 {stats['valid_total']}")
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="JobPulse 增量调度")
    parser.add_argument("--once", action="store_true", help="手动执行一次")
    parser.add_argument("--interval-hours", type=float, default=None, help="定时间隔（小时）")
    parser.add_argument("--source", default="backup", choices=["backup", "job51"])
    args = parser.parse_args()

    cfg = load_config()
    setup_logging(cfg.raw["paths"]["logs_dir"])

    if args.interval_hours:
        from apscheduler.schedulers.blocking import BlockingScheduler

        sched = BlockingScheduler()
        sched.add_job(lambda: incremental_crawl(cfg, args.source),
                      "interval", hours=args.interval_hours,
                      next_run_time=datetime.now())
        print(f"定时调度启动：每 {args.interval_hours} 小时执行增量（Ctrl+C 停止）")
        try:
            sched.start()
        except (KeyboardInterrupt, SystemExit):
            print("调度停止")
        return 0

    incremental_crawl(cfg, args.source)
    return 0


if __name__ == "__main__":
    sys.exit(main())
