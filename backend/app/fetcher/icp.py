"""ICP 备案反查（公司全称 → 官方域名）：作为搜索兜底前的权威映射层。

对接 HG-ha/ICP_Query（github.com/HG-ha/ICP_Query，Python，内置 WebUI 与 JSON API）：
查询路径固定为 {ICP_API_URL}/query/web?search=公司名，响应形如
    { "code": 200, "params": { "list": [ { "serviceName": "example.com", "unitName": "…", ... } ] } }。
未配置（ICP_API_URL 为空）或服务不可达/无记录时优雅降级返回 None（走 Bing 兜底）。

查询结果缓存进本地 SQLite（icp_cache 表），重复查询零网络开销；无记录也缓存，防重复请求。
"""
import json
import logging
import os
import re
import time
from contextlib import closing
from urllib.parse import quote

from .. import config
from ..db import get_conn
from ..util import now_iso
from .http import fetch_json

logger = logging.getLogger("app.fetcher.icp")

TTL_SECONDS = 90 * 24 * 3600  # 缓存 90 天

# 域名形态：字母数字开头的标签，点分，至少含一个字母（排除日期/纯数字串误判）
_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*(\.[a-zA-Z0-9][a-zA-Z0-9\-]*)+$")


def _base_url() -> str:
    """配置优先级：进程环境变量 > app/config.py 的 ICP_API_URL。"""
    return (os.environ.get("ICP_API_URL") or config.ICP_API_URL or "").strip().rstrip("/")


def available() -> bool:
    """是否配置了 ICP 查询服务（未配置则整个模块不工作）。"""
    return bool(_base_url())


def _query_url(name: str) -> str:
    return f"{_base_url()}/query/web?search={quote(name)}"


def _first_domain(values) -> str | None:
    """在未知结构的记录里嗅探第一个像域名的值（不依赖字段名，兼容 MIIT 返回变化）。"""
    for v in values or []:
        if not isinstance(v, str):
            continue
        s = v.strip().lower()
        if _DOMAIN_RE.match(s) and any(c.isalpha() for c in s):
            return s
    return None


def _parse(data) -> dict | None:
    """从 ICP_Query 响应提取域名。兼容常见形态：
    - 标准：{code, params:{list:[{...域名字段...}]}}
    - 简化：{data:{domain|domains}}
    """
    if not isinstance(data, dict):
        return None
    # 形态一：ICP_Query 标准响应 params.list
    params = data.get("params")
    if isinstance(params, dict):
        items = params.get("list")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    domain = _first_domain(item.values())
                    if domain:
                        return {"name": None, "domain": domain, "website": f"https://{domain}"}
    # 形态二：data/result 节点
    node = data.get("data", data.get("result"))
    if isinstance(node, list):
        node = node[0] if node else None
    if isinstance(node, dict):
        domain = _first_domain(node.values())
        if domain:
            return {"name": None, "domain": domain, "website": f"https://{domain}"}
    return None


def _cache_get(name: str) -> dict | None | str:
    try:
        with closing(get_conn()) as conn:
            row = conn.execute(
                "SELECT result, updated_at FROM icp_cache WHERE name = ?", (name,)
            ).fetchone()
    except Exception:
        return "MISS"
    if not row:
        return "MISS"
    if time.time() - _parse_ts(row[1]) > TTL_SECONDS:
        return "MISS"
    return json.loads(row[0]) if row[0] else None


def _cache_set(name: str, result: dict | None) -> None:
    try:
        with closing(get_conn()) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO icp_cache (name, result, updated_at) VALUES (?,?,?) "
                    "ON CONFLICT(name) DO UPDATE SET result=excluded.result, updated_at=excluded.updated_at",
                    (name, json.dumps(result, ensure_ascii=False) if result else None, now_iso()),
                )
    except Exception:
        pass  # 缓存失败不影响查询结果


def _parse_ts(ts: str) -> float:
    try:
        return time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return 0.0


def lookup(name: str) -> dict | None:
    """按公司名查 ICP 备案，返回 {domain, website}；未配置/失败/无记录返回 None。"""
    name = str(name or "").strip()
    if not name or not _base_url():
        return None
    cached = _cache_get(name)
    if cached != "MISS":
        return cached
    try:
        data = fetch_json(_query_url(name), time.monotonic() + 15)
    except Exception as exc:
        logger.info("ICP 查询失败 name=%s %s", name, exc)
        _cache_set(name, None)
        return None
    result = _parse(data)
    _cache_set(name, result)
    return result
