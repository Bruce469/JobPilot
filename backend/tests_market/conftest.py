# -*- coding: utf-8 -*-
"""pytest 公共配置：项目根路径 + 环境变量默认值（合并后 tests_market/）。"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 测试默认使用 SQLite 兜底，避免依赖本机 MySQL
os.environ.setdefault("JOBPULSE_TEST_DB", "sqlite")
os.environ.setdefault("DB_PASSWORD", "123456")


def pytest_configure(config):
    # 注册 live 标记：联网/真实数据源用例（test_live_adapters.py），验收用 -m "not live" 排除
    config.addinivalue_line("markers", "live: 联网测试（默认排除，运行用 -m \"not live\"）")
