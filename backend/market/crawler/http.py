# -*- coding: utf-8 -*-
"""反爬容错基础（REQ-DC-02）：
- UA 池随机轮换
- 随机延时（2~5s）
- 请求重试（3 次，指数退避）
- 403/验证码/封禁不重试，立即停止并告警（R1）
"""
from __future__ import annotations

import logging
import random
import time
from typing import Callable, Optional

import requests

logger = logging.getLogger(__name__)

# UA 池（REQ-DC-02）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# 禁止重试的状态码（403/验证码/封禁 → 立即停止该源并告警）
NO_RETRY_STATUS = {403, 429}
NO_RETRY_MARKERS = ("captcha", "verify", "waf", "访问验证", "安全验证", "滑块")


class BlockedError(Exception):
    """源被封禁/验证码拦截：不重试，立即告警并停止该源（R1）。"""


def random_ua() -> str:
    return random.choice(USER_AGENTS)


def random_delay(min_sec: float = 2, max_sec: float = 5) -> None:
    """随机延时（REQ-DC-02，2~5s）。"""
    time.sleep(random.uniform(min_sec, max_sec))


def is_blocked_response(resp: requests.Response) -> bool:
    """判断响应是否为 403/验证码/封禁/WAF 拦截页。"""
    if resp.status_code in NO_RETRY_STATUS:
        return True
    body = resp.text[:2000].lower()
    return any(m in body for m in NO_RETRY_MARKERS)


def request_with_retry(
    url: str,
    *,
    method: str = "GET",
    retry_times: int = 3,
    backoff: float = 2.0,
    delay_min: float = 0,
    delay_max: float = 0,
    session: Optional[requests.Session] = None,
    **kwargs,
) -> requests.Response:
    """带重试的请求（REQ-DC-02）：
    - 断网/超时/5xx：重试（指数退避）
    - 403/429/验证码：不重试，抛 BlockedError（立即停止该源并告警）
    - 每次请求前随机延时（可选）
    """
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", random_ua())
    kwargs["headers"] = headers
    kwargs.setdefault("timeout", 15)

    sess = session or requests.Session()
    last_exc: Optional[Exception] = None

    for attempt in range(1, retry_times + 1):
        if delay_max > 0:
            random_delay(delay_min, delay_max)
        try:
            resp = sess.request(method, url, **kwargs)
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            logger.warning("请求失败(尝试 %d/%d): %s %s", attempt, retry_times, url, e)
            if attempt < retry_times:
                time.sleep(backoff ** attempt)
            continue

        # 403/验证码/封禁：不重试，立即停止（R1）
        if is_blocked_response(resp):
            logger.error("检测到封禁/验证码(状态 %s): %s — 立即停止该源", resp.status_code, url)
            raise BlockedError(f"{url} 被拦截 (status={resp.status_code})")

        # 5xx 重试
        if resp.status_code >= 500:
            last_exc = RuntimeError(f"HTTP {resp.status_code}: {url}")
            logger.warning("5xx(尝试 %d/%d): %s -> %s", attempt, retry_times, url, resp.status_code)
            if attempt < retry_times:
                time.sleep(backoff ** attempt)
            continue

        return resp

    raise last_exc or RuntimeError(f"请求最终失败: {url}")
