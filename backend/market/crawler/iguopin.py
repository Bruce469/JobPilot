# -*- coding: utf-8 -*-
"""国聘网 adapter（REQ-DC-05）：人社部指导的国企央企招聘平台。

数据源：gp-api.iguopin.com/api/jobs/v1/list（POST，JSON body，公开免登录）
接口验证（2026-02 实测）：
  body={"page":1,"page_size":50,"job_name":"数据分析"} → {"code":200,"data":{total,list}}
  必须携带 Referer/Origin 头；按 job_name 标题模糊匹配（keyword 全文匹配噪声大）。
字段映射（对齐 jobs 表，附录 11.4 模板）：
  job_id         → iguopin_{job_id}
  job_name       → job_title
  nature_cn      → job_type（校招/社招；"校园招聘/社会招聘"归并）
  company_name   → company_name
  category_cn    → classify_category 兜底 label
  district_list  → city（area_cn 取首段，如"石家庄-正定县"→"石家庄"）
  min/max_wage   → salary（wage_unit_cn=元/天 时走 parse_salary 日薪规则）
  education_cn   → education_req（本科/硕士/博士/大专）
  experience_cn  → experience_req（应届生→1年以内）
  contents       → job_desc（去 HTML 标签）
  start_time     → post_date
  —              → url=https://www.iguopin.com/job/detail?id={job_id}
合规：仅低频拉取公开职位列表，不逆向、不绕过验证码（需求 3.2）。
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Iterator, Optional

import requests

from market.crawler.http import BlockedError, random_delay, random_ua, request_with_retry
from market.etl.clean import clean_city, clean_job_type, classify_category
from market.etl.jd_parse import parse_education_from_text, parse_experience_from_text
from market.etl.salary import parse_salary

logger = logging.getLogger(__name__)

SOURCE_ID = "iguopin"
API_URL = "https://gp-api.iguopin.com/api/jobs/v1/list"
JOB_URL_TMPL = "https://www.iguopin.com/job/detail?id={job_id}"
DEFAULT_PAGE_SIZE = 50
DEFAULT_MAX_PAGES = 3
TIMEOUT = 20

# nature_cn 归并（国聘列表字段：校招/社招）
JOB_TYPE_MAP = {
    "校招": "校招", "校园招聘": "校招", "应届": "校招",
    "社招": "社招", "社会招聘": "社招",
}

# experience_cn → 项目枚举（附录 11.5；"应届生/在校生"归入 1年以内）
EXPERIENCE_MAP = {
    "应届生": "1年以内", "在校生": "1年以内", "无经验": "1年以内", "不限": "不限",
    "经验不限": "不限", "1-3年": "1-3年", "3-5年": "3-5年",
    "5-10年": "5-10年", "10年以上": "10年以上",
}

# 保留的数据类岗位（项目主题：数据分析/数据科学/大数据/算法/BI数仓）
# classify_category 对未知岗位兜底"数据分析"，故主题过滤必须基于标题判定
from market.etl.clean import is_data_job_title as _is_data_job_title

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: Optional[str]) -> str:
    """去 HTML 标签 + 空白归一。"""
    if not text:
        return ""
    return _TAG_RE.sub("", text).strip()


def _extract_city(item: dict) -> str:
    """district_list[0].area_cn → 城市（取"-"前首段）。"""
    dists = item.get("district_list") or []
    if not dists:
        return ""
    first = dists[0]
    if isinstance(first, dict):
        area = str(first.get("area_cn") or "").strip()
    else:
        area = str(first).strip()  # 脏数据兜底：直接取元素文本
    if not area:
        return ""
    return area.split("-")[0].strip()


def _safe_int(value) -> Optional[int]:
    """脏数据兜底：非数字字符串 → None（上游接口字段类型漂移时置空而非中断）。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_wage(item: dict, job_type: str):
    """薪资归一化：返回 (salary_raw, salary_min, salary_max, salary_avg, is_valid)。

    - is_negotiable=True 或 min_wage<=0 → 面议（薪资 NULL，保留记录）
    - wage_unit_cn="元/天" → 走 parse_salary 日薪规则（实习×20，全职×21.75）
    - 其余（元/月等）→ 直接以数字区间归一化
    """
    if item.get("is_negotiable"):
        return "", None, None, None, True
    lo = _safe_int(item.get("min_wage"))
    hi = _safe_int(item.get("max_wage"))
    if not lo or lo <= 0:
        return "", None, None, None, True

    unit = str(item.get("wage_unit_cn") or "元/月")
    hi = hi or lo

    if "天" in unit:
        raw = f"{lo}-{hi}元/天"
        pr = parse_salary(raw, job_type)
    else:
        raw = f"{lo}-{hi}"
        pr = parse_salary(raw, job_type)

    if not pr.parse_ok:
        return raw, None, None, None, True
    return raw, pr.salary_min, pr.salary_max, pr.salary_avg, pr.is_valid


def transform_row(idx: int, item: dict, crawl_date: datetime) -> dict:
    """国聘职位 JSON → 统一 Schema dict（对齐 backup.transform_row）。"""
    title = str(item.get("job_name") or "").strip() or "未命名岗位"
    desc = _strip_html(item.get("contents"))
    city = clean_city(_extract_city(item) or None)

    # 岗位类型：优先源端 nature_cn，兜底文本解析
    job_type = JOB_TYPE_MAP.get(str(item.get("nature_cn") or ""), "")
    if not job_type:
        job_type = clean_job_type(title=title, desc=desc)

    salary_raw, smin, smax, savg, sal_valid = _parse_wage(item, job_type)

    # 有效性：国聘为国企央企岗位、城市遍布全国，放宽为"城市可解析即有效"；
    # 薪资异常仍标记无效（与 backup 口径对齐，REQ-4.4）
    is_valid = 1
    if not city or city == "未知":
        is_valid = 0
    if not sal_valid:
        is_valid = 0

    # 学历/经验：优先源端枚举，兜底 JD 文本解析
    edu_cn = str(item.get("education_cn") or "").strip()
    exp_cn = str(item.get("experience_cn") or "").strip()
    education_req = edu_cn or parse_education_from_text(desc) or "不限"
    experience_req = EXPERIENCE_MAP.get(exp_cn, exp_cn) or parse_experience_from_text(desc) or "不限"

    # 岗位大类：JD 文本关键词优先，源端类别兜底
    category = classify_category(
        title=title, desc=desc, label=str(item.get("category_cn") or ""))

    job_id = str(item.get("job_id") or f"idx{idx}")
    start_time = item.get("start_time")
    post_date = None
    if start_time:
        try:
            post_date = datetime.strptime(str(start_time)[:10], "%Y-%m-%d").date()
        except ValueError:
            post_date = None

    return {
        "job_id": f"{SOURCE_ID}_{job_id}",
        "job_title": title,
        "job_category": category,
        "job_type": job_type,
        "company_name": str(item.get("company_name") or "").strip() or "未知公司",
        "industry": "未标注",
        "company_size": None,
        "city": city or "未知",
        "salary_raw": salary_raw,
        "salary_min": smin,
        "salary_max": smax,
        "salary_avg": savg,
        "experience_req": experience_req,
        "education_req": education_req,
        "job_desc": desc,
        "tags": [],
        "post_date": post_date,
        "crawl_date": crawl_date,
        "url": JOB_URL_TMPL.format(job_id=job_id),
        "is_valid": is_valid,
        "source": SOURCE_ID,
    }


class IguopinAdapter:
    """国聘网 adapter：按关键词分页拉取公开职位列表。"""

    source_id = SOURCE_ID

    def __init__(self, keywords: Optional[list[str]] = None,
                 page_size: Optional[int] = None,
                 max_pages: Optional[int] = None,
                 delay_min: float = 2, delay_max: float = 5):
        self.keywords = keywords or []
        self.page_size = page_size or DEFAULT_PAGE_SIZE
        self.max_pages = max_pages or DEFAULT_MAX_PAGES
        self.delay_min = delay_min
        self.delay_max = delay_max

    def fetch_page(self, keyword: str, page: int) -> list[dict]:
        """拉取单页职位列表；被拦截抛 BlockedError（不重试）。

        用 job_name 参数按标题模糊匹配（keyword 为全文匹配，噪声大；
        2026-02 实测 job_name="数据分析" → total=34 且标题全部命中）。
        """
        if self.delay_max > 0:
            random_delay(self.delay_min, self.delay_max)
        resp = request_with_retry(
            API_URL, method="POST",
            headers={
                "Content-Type": "application/json",
                "Origin": "https://www.iguopin.com",
                "Referer": "https://www.iguopin.com/",
                "User-Agent": random_ua(),
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            json={"page": page, "page_size": self.page_size, "job_name": keyword},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            raise BlockedError(f"[{SOURCE_ID}] HTTP {resp.status_code}: {resp.url}")
        try:
            payload = resp.json()
        except ValueError as e:
            raise BlockedError(f"[{SOURCE_ID}] 非 JSON 响应: {e}")
        if payload.get("code") != 200:
            raise BlockedError(f"[{SOURCE_ID}] 接口返回异常: {payload.get('msg')}")
        return payload.get("data", {}).get("list") or []

    def iter_rows(self, crawl_date: Optional[datetime] = None,
                  keywords: Optional[list[str]] = None) -> Iterator[dict]:
        """按关键词 × 分页产出统一 Schema dict。

        keywords 缺省用构造参数；keyword 必填（接口按关键词搜索）。
        """
        crawl_date = crawl_date or datetime.now()
        kws = list(dict.fromkeys(keywords or self.keywords))
        if not kws:
            logger.warning("[%s] 无搜索关键词，跳过", SOURCE_ID)
            return
        total_fetched = 0
        for kw in kws:
            for page in range(1, self.max_pages + 1):
                try:
                    items = self.fetch_page(kw, page)
                except BlockedError as e:
                    logger.error("[%s] 关键词 %r 拉取失败: %s", SOURCE_ID, kw, e)
                    break
                if not items:
                    break
                for idx, it in enumerate(items):
                    row = transform_row(idx, it, crawl_date)
                    if not _is_data_job_title(row["job_title"]):
                        continue  # 只保留数据类岗位（标题主题过滤）
                    yield row
                total_fetched += len(items)
                logger.info("[%s] 关键词 %r 第 %d 页 %d 条（累计 %d）",
                            SOURCE_ID, kw, page, len(items), total_fetched)
                # 到达末页：返回条数 < page_size 即结束该关键词
                if len(items) < self.page_size:
                    break
