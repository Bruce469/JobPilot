# -*- coding: utf-8 -*-
"""采集健康监控（REQ-DC-07）：
按 城市×关键词组合 统计请求成功数/命中数/失败数；
运行结束输出统计表；任一组合 0 命中或整体命中率 < 阈值时输出告警。
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ComboStats:
    requests_ok: int = 0     # 请求成功数
    hits: int = 0            # 命中（解析出岗位）数
    failed: int = 0          # 请求失败数

    @property
    def total(self) -> int:
        return self.requests_ok + self.failed

    @property
    def hit_rate(self) -> float:
        if self.requests_ok == 0:
            return 0.0
        return self.hits / self.requests_ok


class HealthMonitor:
    def __init__(self, alert_hit_rate: float = 0.30):
        self.alert_hit_rate = alert_hit_rate
        self._stats: dict[tuple[str, str], ComboStats] = defaultdict(ComboStats)

    def record_request(self, city: str, keyword: str, ok: bool, hits: int = 0) -> None:
        s = self._stats[(city, keyword)]
        if ok:
            s.requests_ok += 1
            s.hits += hits
        else:
            s.failed += 1

    def summary(self) -> dict:
        """运行结束输出采集统计表；返回统计字典（供报告/告警）。"""
        rows = []
        for (city, kw), s in sorted(self._stats.items()):
            rows.append({
                "city": city, "keyword": kw,
                "requests_ok": s.requests_ok, "hits": s.hits,
                "failed": s.failed, "hit_rate": round(s.hit_rate, 3),
            })
        return {"rows": rows, "alert_hit_rate": self.alert_hit_rate}

    def report(self) -> str:
        """生成可读统计表 + 告警（REQ-DC-07）。"""
        summary = self.summary()
        lines = ["\n===== 采集健康监控统计（城市×关键词）====="]
        lines.append(f"{'城市':<8}{'关键词':<12}{'成功':>6}{'命中':>6}{'失败':>6}{'命中率':>8}")
        total_ok = total_hits = total_failed = 0
        zero_hit_combos = []
        for r in summary["rows"]:
            lines.append(f"{r['city']:<8}{r['keyword']:<12}{r['requests_ok']:>6}"
                         f"{r['hits']:>6}{r['failed']:>6}{r['hit_rate']:>8.1%}")
            total_ok += r["requests_ok"]
            total_hits += r["hits"]
            total_failed += r["failed"]
            if r["hits"] == 0:
                zero_hit_combos.append(f"{r['city']}×{r['keyword']}")

        overall_rate = total_hits / total_ok if total_ok else 0.0
        lines.append("-" * 50)
        lines.append(f"合计: 成功 {total_ok} / 命中 {total_hits} / 失败 {total_failed} / 整体命中率 {overall_rate:.1%}")

        # 告警（REQ-DC-07）
        alert_msgs = []
        if zero_hit_combos:
            alert_msgs.append(f"0 命中组合: {', '.join(zero_hit_combos[:10])}")
        if overall_rate < self.alert_hit_rate:
            alert_msgs.append(f"整体命中率 {overall_rate:.1%} 低于阈值 {self.alert_hit_rate:.0%}")
        for msg in alert_msgs:
            logger.warning("[采集告警] %s", msg)
            lines.append(f"⚠ 告警: {msg}")

        return "\n".join(lines)
