# -*- coding: utf-8 -*-
"""checkpoint 断点续爬（REQ-DC-04）：
- 本地持久化每个 城市×关键词组合 的已完成页码
- 中断后重跑从 checkpoint 处继续，不从头开始
- 仅用于进度恢复；job_id 去重不用于进度恢复（4.2 幂等）
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Checkpoint:
    def __init__(self, checkpoint_dir: str | Path, source: str):
        self.dir = Path(checkpoint_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = self.dir / f"checkpoint_{source}.json"
        self.data: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        if self.file.exists():
            try:
                self.data = json.loads(self.file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("checkpoint 文件损坏，重置: %s (%s)", self.file, e)
                self.data = {}

    def get_page(self, key: str) -> int:
        """返回该组合已完成的最大页码（0 = 未开始）。"""
        return int(self.data.get(key, 0))

    def mark_page_done(self, key: str, page: int) -> None:
        """记录该组合已完成到 page 页。"""
        if page > self.data.get(key, 0):
            self.data[key] = page
            self._save()

    def _save(self) -> None:
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.file)

    def summary(self) -> dict[str, int]:
        return dict(self.data)
