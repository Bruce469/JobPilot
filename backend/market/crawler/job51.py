# -*- coding: utf-8 -*-
"""51job adapter 骨架（REQ-DC-01/05）。

W1 验证结论（2026-02 实测）：
- we.51job.com/api/job/search-pc 返回阿里云 WAF JS 挑战页
- search.51job.com 旧版搜索页返回空页面
- m.51job.com 移动端同样被 WAF 拦截
按需求 3.2 边界（不做逆向破解/绕过验证码）判定该源当前不可用，
保留 adapter 接口以维持可插拔架构（REQ-DC-05），实际调用时给出明确告警。
"""
from __future__ import annotations

import logging
from typing import Iterator

from market.crawler.http import BlockedError

logger = logging.getLogger(__name__)

SOURCE_ID = "job51"
UNAVAILABLE_REASON = (
    "51job 全端点被阿里云 WAF 深度保护（需 JS 执行挑战），"
    "按需求 3.2 边界不做绕过，当前判定不可用；请切换 --source backup"
)


class Job51Adapter:
    """51job adapter：当前不可用（W1 验证），保留接口。"""

    source_id = SOURCE_ID

    def fetch(self, city: str, keyword: str, page: int = 1) -> list[dict]:
        raise BlockedError(f"[{self.source_id}] {UNAVAILABLE_REASON}")

    def iter_rows(self, **kwargs) -> Iterator[dict]:
        raise BlockedError(f"[{self.source_id}] {UNAVAILABLE_REASON}")

    @staticmethod
    def availability() -> str:
        return UNAVAILABLE_REASON
