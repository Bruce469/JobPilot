"""A股上市公司离线信息库（数据源：巨潮资讯 cninfo，由 scripts/build_akshare_company_db.py 生成）。

提供 name/aliases → {website 官网, industry 行业, city 注册城市} 的离线查找；
数据文件缺失时索引为空，lookup 恒返回 None（不阻塞 resolve 流程）。
"""
import json
from pathlib import Path

from .normalize import normalize_company

_DATA_PATH = Path(__file__).resolve().parent / "company_info_data.json"

_INDEX: dict[str, dict] = {}


def _key(s: str) -> str:
    return normalize_company(s).strip().lower()


def load() -> None:
    global _INDEX
    _INDEX = {}
    if not _DATA_PATH.exists():
        return
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            entries = json.load(f)
    except (OSError, ValueError):
        return
    for entry in entries:
        keys = {_key(entry["name"])}
        for alias in entry.get("aliases", []) or []:
            keys.add(_key(alias))
        for k in keys:
            if k:
                _INDEX.setdefault(k, entry)


def lookup(name: str) -> dict | None:
    if not name or not str(name).strip():
        return None
    return _INDEX.get(_key(str(name)))


load()
