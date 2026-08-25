# -*- coding: utf-8 -*-
"""兜底数据源 adapter（REQ-DC-05/06）：
GitHub 开源数据集（Rayair019/Job-posting-data）→ 统一 Schema 导入。

字段映射清单（附录 11.4 模板）：
  jobname      → job_title
  company      → company_name
  salary       → salary_raw（原始文本）；数值经 parse_salary 归一化（4.3 规则）
  city         → city（clean_city；"其他"→ is_valid=0）
  description  → job_desc（经验/学历从文本解析）
  other        → tags（福利标签）+ industry（"行业要求：X"解析）
  label        → job_category（classify_category 兜底）
  —            → job_id = backup_{行号}（源标识_序号）
  —            → job_type = clean_job_type(title)
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

from market.etl.clean import (
    CITY_WHITELIST,
    clean_city,
    clean_job_type,
    classify_category,
)
from market.etl.jd_parse import parse_education_from_text, parse_experience_from_text
from market.etl.salary import parse_salary

logger = logging.getLogger(__name__)

SOURCE_ID = "backup"
SOURCE_URL = "https://github.com/Rayair019/Job-posting-data"
SUPPORTED_EXTS = {".xlsx", ".csv", ".json"}


def _parse_industry(other: Optional[str]) -> str:
    """从 other 解析行业（"行业要求：基金/证券/期货"）；无则"未标注"。"""
    if not other:
        return "未标注"
    m = re.search(r"行业要求[:：]\s*([^\n]+)", other)
    if m:
        ind = m.group(1).strip()
        return ind if ind else "未标注"
    return "未标注"


def _parse_tags(other: Optional[str]) -> list[str]:
    """从 other 提取福利标签（去除行业/语言要求行）。"""
    if not other:
        return []
    tags = []
    for line in other.replace("，", ",").splitlines():
        if re.search(r"行业要求|语言要求", line):
            continue
        for t in line.split(","):
            t = t.strip()
            if t and t not in tags:
                tags.append(t)
    return tags[:20]


def transform_row(idx: int, row: dict, crawl_date: datetime) -> dict:
    """单行转换：原始数据集行 → 统一 Schema dict（4.2）。

    is_valid 判定（4.4 / 11.4）：
    - city 非 10 城白名单（含"其他"）→ 0（缺失关键字段）
    - 薪资解析失败（面议/未知）→ 保留记录但薪资 NULL（规则 5），is_valid 保持 1
    - 薪资异常（规则 6）→ is_valid=0
    """
    title = str(row.get("jobname") or "").strip()
    desc = str(row.get("description") or "").strip()
    other = str(row.get("other") or "").strip() if pd.notna(row.get("other")) else ""
    city = clean_city(str(row.get("city") or "").strip() or None)

    job_type = clean_job_type(title=title, desc=desc)

    # 薪资（规则 1~9）
    salary_raw = str(row.get("salary") or "").strip()
    pr = parse_salary(salary_raw, job_type)
    salary_min = salary_max = salary_avg = None
    if pr.parse_ok:
        if pr.is_valid:
            salary_min, salary_max, salary_avg = pr.salary_min, pr.salary_max, pr.salary_avg
        else:
            # 规则 6：异常薪资 → 记录无效
            logger.warning("[backup:%s] 异常薪资 %r -> %s", idx, salary_raw, pr.note)

    # 城市与有效性
    is_valid = 1
    if not city or city not in CITY_WHITELIST:
        is_valid = 0
    if pr.parse_ok and not pr.is_valid:
        is_valid = 0

    # 经验/学历（JD 文本解析；无法判定 → 不限）
    exp_raw = parse_experience_from_text(desc)
    edu_raw = parse_education_from_text(desc)

    category = classify_category(title=title, desc=desc, label=str(row.get("label") or ""))

    return {
        "job_id": f"{SOURCE_ID}_{idx}",
        "job_title": title or "未命名岗位",
        "job_category": category,
        "job_type": job_type,
        "company_name": str(row.get("company") or "").strip() or "未知公司",
        "industry": _parse_industry(other),
        "company_size": None,            # 数据集无该字段
        "city": city or "未知",
        "salary_raw": salary_raw or "",
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_avg": salary_avg,
        "experience_req": exp_raw or "不限",
        "education_req": edu_raw or "不限",
        "job_desc": desc,
        "tags": _parse_tags(other),
        "post_date": None,
        "crawl_date": crawl_date,
        "url": SOURCE_URL,
        "is_valid": is_valid,
        "source": SOURCE_ID,
    }


class BackupAdapter:
    """兜底数据集 adapter：一次性本地导入。"""

    source_id = SOURCE_ID

    def __init__(self, dataset_path: str | Path):
        self.dataset_path = Path(dataset_path)

    def load(self) -> pd.DataFrame:
        path = self.dataset_path
        if not path.exists():
            raise FileNotFoundError(f"兜底数据集不存在: {path}")
        suffix = path.suffix.lower()
        if suffix == ".xlsx":
            return pd.read_excel(path)
        if suffix == ".csv":
            return pd.read_csv(path)
        if suffix == ".json":
            return pd.read_json(path)
        raise ValueError(f"不支持的数据集格式 {suffix}（支持 {SUPPORTED_EXTS}）")

    def iter_rows(self, crawl_date: Optional[datetime] = None) -> Iterator[dict]:
        """逐行产出统一 Schema dict（供幂等写入 + 快照）。"""
        crawl_date = crawl_date or datetime.now()
        df = self.load()
        logger.info("加载兜底数据集 %s，共 %d 行", self.dataset_path.name, len(df))
        for idx, (_, row) in enumerate(df.iterrows(), start=1):
            yield transform_row(idx, dict(row), crawl_date)

    def import_all(self, crawl_date: Optional[datetime] = None) -> tuple[list[dict], list[dict]]:
        """全量导入：返回 (jobs 行, snapshots 行)。"""
        crawl_date = crawl_date or datetime.now()
        jobs = []
        for r in self.iter_rows(crawl_date):
            jobs.append(r)
        snaps = [
            {
                "job_id": j["job_id"], "crawl_date": crawl_date,
                "salary_min": j["salary_min"], "salary_max": j["salary_max"],
                "salary_avg": j["salary_avg"], "is_valid": j["is_valid"], "url": j["url"],
            }
            for j in jobs
        ]
        return jobs, snaps
