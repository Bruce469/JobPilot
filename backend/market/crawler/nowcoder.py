# -*- coding: utf-8 -*-
"""牛客网 adapter（REQ-DC-05）：校招/实习/社招岗位平台。

数据源：nowpick.nowcoder.com/u/job/search（POST，form-urlencoded，公开免登录）
接口验证（2026-02 实测）：
  data={"page":1,"pageSize":20,"query":"数据分析"}
    → {"code":0,"data":{totalCount,totalPage,currentPage,datas:[...]}}
  必须携带 Origin/Referer 头；body 为 application/x-www-form-urlencoded。
字段映射（对齐 jobs 表，附录 11.4 模板）：
  id             → nowcoder_{id}
  jobName        → job_title
  recruitType    → job_type（1=校招 / 2=实习 / 3=社招）
  user.identity  → company_name（首个 identity.companyName）
  industryName   → industry
  jobCityList    → city
  salaryType/Min/Max/Month → salary（1=日薪元/天；2=千元或元/月，含薪数）
  eduLevel       → education_req 兜底（主信号为 JD 文本解析）
  ext(infos+requirements) → job_desc（经验/学历从文本解析）
  refreshTime    → post_date
  —              → url=https://www.nowcoder.com/jobs/detail/{id}
合规：仅低频拉取公开职位列表，不逆向、不绕过验证码（需求 3.2）。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Iterator, Optional

from market.crawler.http import BlockedError, random_delay, random_ua, request_with_retry
from market.etl.clean import CITY_WHITELIST, clean_city, classify_category
from market.etl.jd_parse import parse_education_from_text, parse_experience_from_text
from market.etl.salary import parse_salary

logger = logging.getLogger(__name__)

SOURCE_ID = "nowcoder"
API_URL = "https://nowpick.nowcoder.com/u/job/search"
JOB_URL_TMPL = "https://www.nowcoder.com/jobs/detail/{job_id}"
DEFAULT_PAGE_SIZE = 20
DEFAULT_MAX_PAGES = 5
TIMEOUT = 20

# recruitType → 项目枚举（1=校招 2=实习 3=社招）
RECRUIT_TYPE_MAP = {1: "校招", 2: "实习", 3: "社招"}

# eduLevel 枚举兜底映射（1000=博士 2000=硕士 3000=本科 4000=大专；
# 5000/6000/0 为未指定或"学历不限"，由 JD 文本解析兜底）
EDU_LEVEL_MAP = {
    1000: "博士", 2000: "硕士", 3000: "本科", 4000: "大专",
    5000: "不限", 6000: "不限", 0: "不限",
}

# 未知薪资占位（牛客用 0 / 9999999 表示面议）
_SALARY_UNKNOWN = {0, 9999999}

# 保留的数据类岗位（项目主题：数据分析/数据科学/大数据/算法/BI数仓）
# classify_category 对未知岗位兜底"数据分析"，故主题过滤必须基于标题判定
from market.etl.clean import is_data_job_title as _is_data_job_title


def _parse_ext(ext: Optional[str]) -> tuple[str, str]:
    """ext JSON 字符串 → (infos, requirements) 文本。"""
    if not ext:
        return "", ""
    try:
        data = json.loads(ext)
    except (ValueError, TypeError):
        return "", ""
    infos = str(data.get("infos") or "").strip()
    reqs = str(data.get("requirements") or "").strip()
    return infos, reqs


def _extract_company(item: dict) -> str:
    """company_name：优先 user.identity[].companyName。"""
    user = item.get("user") or {}
    identities = user.get("identity") or []
    if identities:
        name = str(identities[0].get("companyName") or "").strip()
        if name:
            return name
    return ""


def _parse_wage(item: dict, job_type: str):
    """薪资归一化：返回 (salary_raw, salary_min, salary_max, salary_avg, is_valid)。

    - salaryType=1：日薪（元/天），走 parse_salary 日薪规则（实习×20）
    - salaryType=2：max<1000 → 千元区间（20K-30K·15薪）；否则为元/月数字区间
    - min/max 为 0 或 9999999 → 面议
    """
    stype = _safe_int(item.get("salaryType")) or 0
    smin = _safe_int(item.get("salaryMin")) or 0
    smax = _safe_int(item.get("salaryMax")) or 0
    months = _safe_int(item.get("salaryMonth")) or 0

    if stype == 0 or smin in _SALARY_UNKNOWN or smax in _SALARY_UNKNOWN:
        return "", None, None, None, True

    if stype == 1:
        raw = f"{smin}-{smax}元/天"
        pr = parse_salary(raw, job_type)
        if not pr.parse_ok:
            return raw, None, None, None, True
        return raw, pr.salary_min, pr.salary_max, pr.salary_avg, pr.is_valid

    if smax < 1000:
        # 千元区间，如 20-30K·15薪
        raw = f"{smin}-{smax}K·{months}薪" if months and months != 12 else f"{smin}-{smax}K"
        pr = parse_salary(raw, job_type)
        if not pr.parse_ok:
            return raw, None, None, None, True
        return raw, pr.salary_min, pr.salary_max, pr.salary_avg, pr.is_valid

    # 元/月数字区间：薪数 != 12 时按 月薪×12/薪数 折算（与 parse_salary 规则 1/4 同口径）
    if months and months != 12:
        smin_m = round(smin * 12 / months)
        smax_m = round(smax * 12 / months)
        raw = f"{smin}-{smax}元·{months}薪"
        return raw, smin_m, smax_m, round((smin_m + smax_m) / 2), True

    raw = f"{smin}-{smax}"
    pr = parse_salary(raw, job_type)
    if not pr.parse_ok:
        return raw, None, None, None, True
    return raw, pr.salary_min, pr.salary_max, pr.salary_avg, pr.is_valid


def _safe_int(value) -> int | None:
    """脏数据兜底：非数字字符串 → None。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def transform_row(idx: int, item: dict, crawl_date: datetime) -> dict:
    """牛客职位 JSON → 统一 Schema dict（对齐 backup.transform_row）。"""
    title = str(item.get("jobName") or "").strip() or "未命名岗位"
    infos, reqs = _parse_ext(item.get("ext"))
    desc = "\n".join(x for x in (infos, reqs) if x)
    city = clean_city((item.get("jobCityList") or [item.get("jobCity")] or [""])[0] or None)

    job_type = RECRUIT_TYPE_MAP.get(int(item.get("recruitType") or 0), "不限")

    salary_raw, smin, smax, savg, sal_valid = _parse_wage(item, job_type)

    is_valid = 1
    if not city or city not in CITY_WHITELIST:
        is_valid = 0
    if not sal_valid:
        is_valid = 0

    # 学历/经验：JD 文本解析优先，eduLevel 兜底
    education_req = parse_education_from_text(desc) \
        or EDU_LEVEL_MAP.get(int(item.get("eduLevel") or 0), "不限")
    experience_req = parse_experience_from_text(desc) or "不限"

    category = classify_category(title=title, desc=desc, label="")

    job_id = str(item.get("id") or f"idx{idx}")

    # 发布时间：refreshTime/updateTime（毫秒时间戳）→ 日期（东八区）
    from datetime import timedelta, timezone as tz_mod

    tz8 = tz_mod(timedelta(hours=8))
    post_date = None
    for key in ("refreshTime", "updateTime"):
        ts = item.get(key)
        if ts:
            try:
                post_date = datetime.fromtimestamp(int(ts) / 1000, tz=tz8).date()
                break
            except (ValueError, OSError):
                continue

    return {
        "job_id": f"{SOURCE_ID}_{job_id}",
        "job_title": title,
        "job_category": category,
        "job_type": job_type,
        "company_name": _extract_company(item) or "未知公司",
        "industry": str(item.get("industryName") or "").strip() or "未标注",
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


class NowcoderAdapter:
    """牛客网 adapter：按关键词分页拉取公开职位列表。"""

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
        """拉取单页职位列表；被拦截抛 BlockedError（不重试）。"""
        if self.delay_max > 0:
            random_delay(self.delay_min, self.delay_max)
        resp = request_with_retry(
            API_URL, method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://www.nowcoder.com",
                "Referer": "https://www.nowcoder.com/job/center",
                "User-Agent": random_ua(),
            },
            data={"page": page, "pageSize": self.page_size, "query": keyword},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            raise BlockedError(f"[{SOURCE_ID}] HTTP {resp.status_code}: {resp.url}")
        try:
            payload = resp.json()
        except ValueError as e:
            raise BlockedError(f"[{SOURCE_ID}] 非 JSON 响应: {e}")
        if payload.get("code") != 0:
            raise BlockedError(f"[{SOURCE_ID}] 接口返回异常: {payload.get('msg')}")
        return payload.get("data", {}).get("datas") or []

    def iter_rows(self, crawl_date: Optional[datetime] = None,
                  keywords: Optional[list[str]] = None) -> Iterator[dict]:
        """按关键词 × 分页产出统一 Schema dict。"""
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
                if len(items) < self.page_size:
                    break
