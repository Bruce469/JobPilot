"""限速器（架构 5.5）：全局 ≤30 请求/分钟 + 同域间隔 ≥1.5s。"""
import threading
import time
from urllib.parse import urlparse

MIN_DOMAIN_INTERVAL = 1.5   # 秒
GLOBAL_PER_MINUTE = 30


class RateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._domain_last: dict[str, float] = {}
        self._slots: list[float] = []  # 最近请求时间戳（全局桶）

    def wait(self, url: str) -> None:
        host = urlparse(url).netloc.lower()
        with self._lock:
            now = time.monotonic()
            # 同域间隔
            last = self._domain_last.get(host)
            wait = 0.0
            if last is not None:
                gap = now - last
                if gap < MIN_DOMAIN_INTERVAL:
                    wait = max(wait, MIN_DOMAIN_INTERVAL - gap)
            # 全局桶
            self._slots = [t for t in self._slots if t > now - 60]
            if len(self._slots) >= GLOBAL_PER_MINUTE:
                wait = max(wait, self._slots[0] + 60 - now)
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._domain_last[host] = now
            self._slots = [t for t in self._slots if t > now - 60]
            self._slots.append(now)


rate_limiter = RateLimiter()
