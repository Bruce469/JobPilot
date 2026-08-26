# -*- coding: utf-8 -*-
"""一次性/可重跑脚本：合并 guoyang-pro 央企国企名录（https://github.com/HA7CH/guoyang-pro，MIT）进内置公司映射表。

规则：
- 名录公司若与现有映射（名称/简称/别名归一化后）冲突 → 跳过（现有条目更完整，含官网）。
- 新增条目：name=公司全称，aliases=简称+原别名，career_url=名录招聘站 recruit_site，
  industry=行业映射（sector→本项目行业词表），city=总部城市 hq，nature=按监管单位判 央企/国企。
- 官网 website 名录未提供 → 留空串，运行时由搜索兜底补全（resolve 对缺官网的映射命中会继续搜索）。
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.fetcher.normalize import normalize_company  # noqa: E402

ROSTER = Path(__file__).resolve().parent / "roster_raw.json"
TARGET = Path(__file__).resolve().parent.parent / "app" / "fetcher" / "company_map_data.json"
ROSTER_URL = "https://raw.githubusercontent.com/HA7CH/guoyang-pro/master/cli/data/enterprises/roster.json"

# 行业映射：名录 sector → 本项目行业词表（与 INDUSTRY_KEYWORDS / 现有映射一致）
SECTOR_MAP = {
    "交通运输": "物流", "能源电力": "能源", "其他": None, "证券保险": "金融",
    "金融银行": "金融", "建筑工程": "地产", "航空航天军工": "制造", "钢铁有色": "制造",
    "建材机械": "制造", "油气化工": "能源", "烟草": "能源", "电信运营": "通信",
    "商贸物流": "物流", "汽车制造": "汽车", "科技数字": "科技", "农业粮食": "快消",
    "医药健康": "医药",
}
# 性质映射：监管单位 → 公司性质
NATURE_MAP = {
    "国务院国资委": "央企", "财政部": "央企", "国家烟草专卖局": "央企",
    "国铁集团": "央企", "地方国资委": "国企",
}
# 名录缺失总部城市但已知的常用企业 → 补全（其余保持 null，运行时由搜索尽力提取）
HQ_FIX = {
    "中国五矿集团有限公司": "北京", "中国东方电气集团有限公司": "成都", "中国一重集团有限公司": "齐齐哈尔",
    "中国盐业集团有限公司": "北京", "中国有色矿业集团有限公司": "北京", "中国机械工业集团有限公司": "北京",
    "哈尔滨电气集团有限公司": "哈尔滨", "中国机械科学研究总院集团有限公司": "北京", "矿冶科技集团有限公司": "北京",
    "中国钢研科技集团有限公司": "北京", "中国有研科技集团有限公司": "北京", "中国检验认证（集团）有限公司": "北京",
    "中国国际技术智力合作集团有限公司": "北京", "中国国际工程咨询有限公司": "北京", "中国农业发展集团有限公司": "北京",
    "中国林业集团有限公司": "北京", "中国建筑科学研究院有限公司": "北京", "中国建设科技有限公司": "北京",
    "中国煤炭科工集团有限公司": "北京", "中国煤炭地质总局": "北京", "中国冶金地质总局": "北京",
    "中国安能建设集团有限公司": "北京", "中国融通资产管理集团有限公司": "北京", "中国南水北调集团有限公司": "北京",
    "中国航空器材集团有限公司": "北京", "新兴际华集团有限公司": "北京", "中国资源循环集团有限公司": "天津",
    "中国雅江集团有限公司": "成都", "南光（集团）有限公司": "澳门",
    "中国铁路上海局集团有限公司": "上海", "中国铁路北京局集团有限公司": "北京",
    "中国铁路广州局集团有限公司": "广州", "中国铁路成都局集团有限公司": "成都",
    "中国铁路武汉局集团有限公司": "武汉", "中国铁路沈阳局集团有限公司": "沈阳",
    "中国铁路济南局集团有限公司": "济南", "中国铁路西安局集团有限公司": "西安",
    "中国铁路郑州局集团有限公司": "郑州", "中国铁路哈尔滨局集团有限公司": "哈尔滨",
}


def _is_placeholder(r: dict) -> bool:
    """名录中的集合占位条目（非真实单家公司）直接过滤。"""
    name = r.get("name") or ""
    return "/" in name or "等" in name or name.startswith("各省") or name.startswith("各市")


def _keys(entry: dict) -> set:
    """现有映射条目的全部归一化键（名称 + 别名）。"""
    keys = {normalize_company(entry["name"])}
    for alias in entry.get("aliases", []) or []:
        keys.add(normalize_company(alias))
    return keys


def main() -> None:
    if not ROSTER.exists():
        print("下载名录数据（MIT，guoyang-pro）...")
        req = urllib.request.Request(ROSTER_URL, headers={"User-Agent": "Mozilla/5.0"})
        ROSTER.write_bytes(urllib.request.urlopen(req, timeout=30).read())
    with open(ROSTER, encoding="utf-8") as f:
        roster = json.load(f)["enterprises"]
    with open(TARGET, encoding="utf-8") as f:
        entries = json.load(f)
    # 幂等：先剥离上一轮合并的名录条目（website 为空串即名录派生），保留手工 curated 基础
    entries = [e for e in entries if e.get("website")]

    existing_keys: set = set()
    for e in entries:
        existing_keys |= _keys(e)

    added = skipped = filtered = 0
    new_entries = []
    for r in roster:
        if _is_placeholder(r):
            filtered += 1
            continue
        candidates = [r["name"], r.get("short"), *(r.get("aliases") or [])]
        if any(normalize_company(c) in existing_keys for c in candidates if c):
            skipped += 1
            continue
        aliases = []
        for a in [r.get("short"), *(r.get("aliases") or [])]:
            if a and a != r["name"] and a not in aliases:
                aliases.append(a)
        new_entries.append({
            "name": r["name"],
            "aliases": aliases,
            "website": "",
            "career_url": r.get("recruit_site") or None,
            "industry": SECTOR_MAP.get(r["sector"]),
            "city": r.get("hq") or HQ_FIX.get(r["name"]),
            "nature": NATURE_MAP.get(r["regulator"]),
        })
        existing_keys |= _keys(new_entries[-1])
        added += 1

    entries.extend(new_entries)
    with open(TARGET, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"新增 {added} 家，跳过 {skipped} 家（与现有映射冲突），过滤占位 {filtered} 家，共 {len(entries)} 家")


if __name__ == "__main__":
    main()
