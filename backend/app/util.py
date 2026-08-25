"""通用工具：本地时间文本 / UUID。"""
import uuid
from datetime import datetime


def now_iso() -> str:
    """本地 datetime 文本 YYYY-MM-DDTHH:MM:SS（不存时区偏移）。"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def today_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def date_of(s: str) -> str:
    """取 datetime/date 文本的日期部分 YYYY-MM-DD。"""
    return (s or "")[:10]


def new_id() -> str:
    return uuid.uuid4().hex


def parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s), fmt)
        except ValueError:
            continue
    return None
