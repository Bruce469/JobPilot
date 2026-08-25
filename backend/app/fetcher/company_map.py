"""内置常见公司映射表（PRD 4.12）：数据驱动（company_map_data.json，便于增补）。

lookup(name) 匹配规则：
- 公司名归一化匹配（复用 normalize.normalize_company，去「有限公司/股份/（中国）」等后缀）
- 别名匹配（中文别名 / 英文名 / 常见写法，大小写不敏感）
- 输入首尾空白与全半角差异在归一化时消除
"""
import json
from pathlib import Path

from .normalize import normalize_company

_DATA_PATH = Path(__file__).resolve().parent / "company_map_data.json"

_ENTRIES: list[dict] = []
_INDEX: dict[str, dict] = {}


def _key(s: str) -> str:
    """索引键：归一化 + 小写（英文别名大小写不敏感）。"""
    return normalize_company(s).strip().lower()


def load() -> None:
    global _ENTRIES, _INDEX
    with open(_DATA_PATH, encoding="utf-8") as f:
        _ENTRIES = json.load(f)
    _INDEX = {}
    for entry in _ENTRIES:
        keys = {_key(entry["name"])}
        for alias in entry.get("aliases", []) or []:
            keys.add(_key(alias))
        for k in keys:
            if k:
                _INDEX.setdefault(k, entry)


def lookup(name: str) -> dict | None:
    """按公司名/别名查找映射条目；未命中返回 None。"""
    if not name or not str(name).strip():
        return None
    return _INDEX.get(_key(str(name)))


def all_entries() -> list[dict]:
    return [dict(e) for e in _ENTRIES]


load()
