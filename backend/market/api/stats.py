# -*- coding: utf-8 -*-
"""看板聚合纯函数（服务端聚合，供 /api/jobs/summary 使用）。

把原单 HTML 看板前端 JS 的统计逻辑（market/viz/dashboard.py 内嵌脚本）搬到后端，
前端只负责渲染 ECharts。records 结构沿用 build_dashboard_data 的轻量投影：
{c: city, g: job_category, e: education_req, s: salary_avg, sk: [skills]}
"""
from __future__ import annotations

import math
from typing import Any, Iterable


def filter_records(records: list[dict], city: str | None = None,
                   category: str | None = None, education: str | None = None,
                   source: str | None = None) -> list[dict]:
    """按 城市 / 岗位类别 / 学历 / 数据源 过滤（None/空串 表示不过滤）。"""
    out = []
    for r in records:
        if city and r["c"] != city:
            continue
        if category and r["g"] != category:
            continue
        if education and r["e"] != education:
            continue
        if source and r.get("src") != source:
            continue
        out.append(r)
    return out


def stats(records: list[dict]) -> dict:
    """筛选后概览统计：岗位数 / 平均月薪 / 月薪中位数。"""
    total = len(records)
    sals = sorted(r["s"] for r in records if r.get("s") is not None)
    mean = int(round(sum(sals) / len(sals))) if sals else 0
    median = sals[len(sals) // 2] if sals else 0
    return {"total": total, "mean_salary": mean, "median_salary": median}


def salary_hist(records: list[dict], n_bins: int = 15) -> dict:
    """薪资分布直方图：bins 为各区间下界，counts 为频数，step 为区间宽。"""
    sals = [r["s"] for r in records if r.get("s") is not None]
    if not sals:
        return {"bins": [], "counts": [], "step": 0}
    lo, hi = min(sals), max(sals)
    step = max(1, math.ceil((hi - lo) / n_bins))
    bins = [lo + i * step for i in range(n_bins)]
    counts = [0] * n_bins
    for s in sals:
        idx = min(n_bins - 1, (s - lo) // step)
        counts[idx] += 1
    return {"bins": bins, "counts": counts, "step": step}


def city_salary(records: list[dict]) -> dict:
    """城市月薪中位数对比。"""
    agg: dict[str, list[int]] = {}
    for r in records:
        s = r.get("s")
        if s is None:
            continue
        agg.setdefault(r["c"], []).append(s)
    cities = sorted(agg)
    medians = [sorted(agg[c])[len(agg[c]) // 2] for c in cities]
    return {"cities": cities, "medians": medians}


def skill_top(records: list[dict], k: int = 15) -> list[dict]:
    """技能需求 Top（命中岗位占比口径，与 NLP 模块一致）。"""
    cnt: dict[str, int] = {}
    for r in records:
        for sk in r.get("sk") or []:
            cnt[sk] = cnt.get(sk, 0) + 1
    total = len(records) or 1
    top = sorted(cnt.items(), key=lambda kv: kv[1], reverse=True)[:k]
    return [{"name": n, "count": c, "ratio": round(c / total, 4)} for n, c in top]


def category_dist(records: list[dict]) -> list[dict]:
    """岗位量占比（按类别，降序）。"""
    agg: dict[str, int] = {}
    for r in records:
        agg[r["g"]] = agg.get(r["g"], 0) + 1
    items = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
    return [{"name": n, "value": v} for n, v in items]


def heatmap(records: list[dict], categories: Iterable[str],
            cities: Iterable[str]) -> dict:
    """城市 × 岗位类别 岗位量热力图：data 为 [j, i, count]（i=城市下标, j=类别下标）。"""
    cats, cms = list(categories), list(cities)
    data = []
    for j, gj in enumerate(cats):
        for i, ci in enumerate(cms):
            cnt = sum(1 for r in records if r["c"] == ci and r["g"] == gj)
            if cnt:
                data.append([j, i, cnt])
    return {"x": cats, "y": cms, "data": data}


def build_charts(records: list[dict], categories: Iterable[str],
                 cities: Iterable[str]) -> dict:
    """一次算齐 5 个图表模块的聚合数据。"""
    return {
        "salary_hist": salary_hist(records),
        "city_salary": city_salary(records),
        "skill_top": skill_top(records),
        "category_dist": category_dist(records),
        "heatmap": heatmap(records, categories, cities),
    }
