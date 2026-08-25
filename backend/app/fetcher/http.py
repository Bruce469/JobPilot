"""httpx 客户端封装：固定 UA、单请求超时 <10s、经限速器放行、robots 检查。"""
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import httpx

from .errors import FetchError, TaskTimeout
from .rate_limiter import rate_limiter

UA = "JobHunter/1.0 (personal-use job tracker; +local)"
TIMEOUT = 10.0
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"}


def _request(url: str, deadline=None, method: str = "GET") -> httpx.Response:
    _check_deadline(deadline, url)
    rate_limiter.wait(url)
    _check_deadline(deadline, url)
    try:
        return httpx.request(method, url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
    except httpx.TimeoutException:
        raise FetchError("TIMEOUT", f"请求超时：{url}")
    except httpx.HTTPError as exc:
        raise FetchError("FETCH_ERROR", f"请求失败：{exc}")


def _check_deadline(deadline, url: str) -> None:
    if deadline is not None and time.monotonic() > deadline:
        raise TaskTimeout(f"任务超时（60s），已放弃请求 {url}")


def fetch(url: str, deadline=None) -> httpx.Response:
    resp = _request(url, deadline)
    if resp.status_code >= 400:
        raise FetchError("HTTP_STATUS", f"HTTP {resp.status_code}：{url}")
    return resp


def fetch_text(url: str, deadline=None) -> str:
    return fetch(url, deadline).text


def fetch_json(url: str, deadline=None) -> dict:
    resp = fetch(url, deadline)
    try:
        return resp.json()
    except ValueError:
        raise FetchError("PARSE_ERROR", f"响应不是合法 JSON：{url}")


def robots_allowed(url: str, deadline=None) -> bool:
    """按 robots.txt 判断该 URL 是否允许抓取；拿不到 robots 视为允许。"""
    origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    rp = urllib.robotparser.RobotFileParser()
    try:
        resp = _request(urljoin(origin, "/robots.txt"), deadline)
        if resp.status_code >= 400:
            return True
        rp.parse(resp.text.splitlines())
    except (FetchError, TaskTimeout):
        return True
    return rp.can_fetch(UA, urlparse(url).path or "/")
