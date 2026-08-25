# -*- coding: utf-8 -*-
"""adapter 工厂（REQ-DC-05）：按 --source 参数切换数据源，至少 2 源可插拔。"""
from __future__ import annotations

from typing import Union

from market.config import Config
from market.crawler.backup import BackupAdapter
from market.crawler.iguopin import IguopinAdapter
from market.crawler.job51 import Job51Adapter
from market.crawler.nowcoder import NowcoderAdapter

Adapter = Union[BackupAdapter, Job51Adapter, IguopinAdapter, NowcoderAdapter]

SUPPORTED_SOURCES = ("backup", "job51", "iguopin", "nowcoder")


def _expand_keywords(cfg: Config) -> list[str]:
    """岗位大类关键词展开（附录 11.2 映射 → 去重后的搜索词列表）。"""
    kws = []
    for cat, words in (cfg.raw["crawler"].get("categories") or {}).items():
        kws.extend(words)
    return list(dict.fromkeys(w for w in kws if w))


def get_adapter(source: str, cfg: Config) -> Adapter:
    """返回数据源 adapter。

    - backup: 兜底 GitHub 数据集（本地导入）
    - job51: 51job（W1 验证被 WAF 拦截，不可用，保留接口）
    - iguopin: 国聘网（gp-api 公开接口，国企央企岗位）
    - nowcoder: 牛客网（nowpick 公开接口，校招/实习/社招）
    """
    source = (source or "").lower()
    crawler_cfg = cfg.raw["crawler"]
    if source == "backup":
        return BackupAdapter(crawler_cfg["backup_dataset"])
    if source == "job51":
        return Job51Adapter()
    if source in ("iguopin", "nowcoder"):
        live = (crawler_cfg.get("live_sources") or {}).get(source, {})
        cls = IguopinAdapter if source == "iguopin" else NowcoderAdapter
        return cls(
            keywords=_expand_keywords(cfg),
            page_size=int(live.get("page_size", 0) or 0) or None,
            max_pages=int(live.get("max_pages", 0) or 0) or None,
            delay_min=float(crawler_cfg.get("delay_min", 2)),
            delay_max=float(crawler_cfg.get("delay_max", 5)),
        )
    raise ValueError(f"未知数据源 {source!r}，可选: {SUPPORTED_SOURCES}")

