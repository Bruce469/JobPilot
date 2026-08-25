# -*- coding: utf-8 -*-
"""统一日志配置（REQ-SCHED-02）：控制台 + 时间戳日志文件。"""
from __future__ import annotations

import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(logs_dir: str | Path = "logs", level: int = logging.INFO) -> str:
    """配置根日志：控制台 + 文件双输出。返回日志文件路径。"""
    global _configured
    log_dir = Path(logs_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"jobpulse_{ts}.log"

    # 避免重复配置（如 pytest 多次调用）
    if _configured:
        return str(log_file)

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    _configured = True
    return str(log_file)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
