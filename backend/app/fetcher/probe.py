"""探测分层（架构 5.3）：robots → 首页链接 → sitemap → 常见招聘子域候选。"""
import gzip
import io
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from .errors import FetchError, TaskTimeout
from .http import fetch, fetch_text, UA

HOME_HREF_KEYWORDS = ("careers", "career", "jobs", "job", "recruit", "招聘", "加入我们")
SITEMAP_KEYWORDS = ("career", "job", "recruit")
SUBDOMAINS = ("talent", "campus", "careers", "jobs", "join", "recruit")
MAX_CANDIDATES = 20
CONF_HIGH = "high"
CONF_MED = "medium"
CONF_LOW = "low"


def _origin_of(url: str) -> str | None:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    return f"{p.scheme}://{p.netloc}"


def _add(candidates: list, url: str, confidence: str, source: str, reason: str) -> None:
    if len(candidates) >= MAX_CANDIDATES:
        return
    if not any(c["url"] == url for c in candidates):
        candidates.append({"url": url, "confidence": confidence, "source": source, "reason": reason})


def _fetch_robots(origin: str, deadline):
    """返回 (RobotFileParser|None, sitemap url 列表)。robots 不可得视为允许。"""
    rp = urllib.robotparser.RobotFileParser()
    try:
        resp = fetch(urljoin(origin, "/robots.txt"), deadline)
    except (FetchError, TaskTimeout):
        return None, []
    if resp.status_code >= 400:
        return None, []
    text = resp.text
    rp.parse(text.splitlines())
    sitemaps = [line.split(":", 1)[1].strip() for line in text.splitlines()
                if line.lower().startswith("sitemap:")]
    return rp, sitemaps


def probe_company(website: str, deadline=None, light: bool = False) -> tuple[list, str | None, str | None]:
    """返回 (candidates, error_code, error_message)；error 非空表示任务应 failed。

    light=True 时只做 robots 检查 + 首页链接扫描（跳过 sitemap 与子域探测），
    用于「按名称自动补全」的搜索兜底，控制单公司耗时。
    """
    origin = _origin_of(website)
    if not origin:
        return [], "INVALID_URL", "官网地址无效"
    candidates: list = []

    # 1) robots.txt：Disallow 招聘页则直接停止
    rp, sitemaps = _fetch_robots(origin, deadline)
    if rp and not rp.can_fetch(UA, "/"):
        return [], "ROBOTS_DISALLOW", "robots.txt 禁止抓取"
    if rp:
        test_paths = ["/careers", "/jobs", "/recruit", "/join", "/career", "/job"]
        if not any(rp.can_fetch(UA, p) for p in test_paths):
            return [], "ROBOTS_DISALLOW", "robots.txt 禁止抓取招聘页"

    # 2) 首页链接扫描
    try:
        html = fetch_text(origin + "/", deadline)
    except (FetchError, TaskTimeout):
        html = None
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            text = a.get_text(" ", strip=True).lower()
            if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
                continue
            hay = f"{href.lower()} {text}"
            if not any(k in hay for k in HOME_HREF_KEYWORDS):
                continue
            url = urljoin(origin, href)
            conf = _href_confidence(href, text)
            if conf:
                _add(candidates, url, conf, "homepage", f"首页链接含 {href}")

    if not light:
        # 3) Sitemap 解析（robots 给出的 + 默认 /sitemap.xml），预算在全部文件间共享
        sitemap_urls = list(sitemaps) if sitemaps else [urljoin(origin, "/sitemap.xml")]
        budget = {"files": 0, "urls": 0}
        for sm in sitemap_urls[:5]:
            try:
                resp = fetch(sm, deadline)
            except (FetchError, TaskTimeout):
                continue
            for u in _parse_sitemap(resp.content, deadline, sm, origin, budget=budget):
                if any(k in u.lower() for k in SITEMAP_KEYWORDS):
                    _add(candidates, u, CONF_HIGH, "sitemap", f"来自 sitemap {sm}")

        # 4) 常见招聘子域候选（仅探测可访问性，置信度 low）
        domain = urlparse(origin).netloc.split(":")[0]
        for sub in SUBDOMAINS:
            u = f"https://{sub}.{domain}/"
            try:
                resp = fetch(u, deadline)
                if resp.status_code == 200:
                    _add(candidates, u, CONF_LOW, "subdomain", f"常见招聘子域 {sub}.{domain}")
            except (FetchError, TaskTimeout):
                continue

    # 置信度降序（high → medium → low）
    order = {CONF_HIGH: 0, CONF_MED: 1, CONF_LOW: 2}
    candidates.sort(key=lambda c: order.get(c["confidence"], 9))
    return candidates, None, None


def _href_confidence(href: str, text: str) -> str | None:
    low = href.lower()
    if "careers" in low or "jobs" in low or "job" in low:
        return CONF_HIGH
    if "recruit" in low or "招聘" in low or "加入我们" in text:
        return CONF_MED
    if "career" in low:
        return CONF_MED
    return None


def _parse_sitemap(content: bytes, deadline, sm: str, origin: str, depth: int = 0,
                   budget: dict | None = None) -> list[str]:
    """解析 sitemap(.xml/.gz)，递归展开 sitemapindex，返回 URL 列表。

    预算控制：子 sitemap 文件累计 ≤ 10 个、URL 条目累计 ≤ 2000 条，防单公司探测失控。
    """
    if budget is None:
        budget = {"files": 0, "urls": 0}
    if depth > 1 or budget["files"] >= 10:
        return []
    budget["files"] += 1
    try:
        if content[:2] == b"\x1f\x8b":
            content = gzip.decompress(content)
        root = ElementTree.fromstring(content)
    except Exception:
        return []
    urls = []
    for child in root:
        tag = child.tag.rsplit("}", 1)[-1].lower()
        if tag == "sitemap":
            loc = child.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc") or ""
            if loc:
                try:
                    resp = fetch(loc, deadline)
                    urls.extend(_parse_sitemap(resp.content, deadline, loc, origin, depth + 1, budget))
                except (FetchError, TaskTimeout):
                    continue
        elif tag == "url":
            loc = child.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc") or ""
            if loc and budget["urls"] < 2000:
                budget["urls"] += 1
                urls.append(loc)
    return urls
