"""公司库筛选单测：list_companies 按 city/industry/nature/keyword 组合过滤。

city/industry 为多值精确 IN 语义（列表或逗号字符串在路由层拆分后传入列表），
单值兼容旧调用（字符串 "北京" 等价于 ["北京"]）；nature/keyword 保持单值语义不变。
"""
from app.dao import create_company, list_companies


def _add(name: str, **kw):
    create_company({"name": name, "website": "https://x.com", **kw})


def test_list_companies_no_filter_returns_all(app_db):
    _add("字节跳动", industry="互联网", city="北京", nature="私企", created_at="2026-01-01T00:00:00")
    _add("国家电网", industry="能源", city="北京", nature="央企", created_at="2026-01-02T00:00:00")
    _add("腾讯", industry="互联网", city="深圳", nature="私企", created_at="2026-01-03T00:00:00")
    assert len(list_companies()) == 3
    assert list_companies()[0]["name"] == "腾讯"  # created_at DESC 序


def test_filter_by_city_multi_exact(app_db):
    """城市多值精确 IN：前缀不再匹配（"北" 不命中"北京"），多值 OR 命中。"""
    _add("字节跳动", city="北京")
    _add("国家电网", city="北京")
    _add("腾讯", city="深圳")
    assert len(list_companies({"city": ["北京"]})) == 2          # 单值精确命中
    assert len(list_companies({"city": ["北"]})) == 0            # 前缀不再模糊命中
    assert len(list_companies({"city": ["北京", "深圳"]})) == 3  # 多值 OR
    assert len(list_companies({"city": ["上海"]})) == 0


def test_filter_by_industry_multi(app_db):
    """行业多值精确 IN，OR 语义。"""
    _add("字节跳动", industry="互联网")
    _add("国家电网", industry="能源")
    _add("腾讯", industry="互联网")
    _add("中石化", industry="能源")
    assert len(list_companies({"industry": ["互联网"]})) == 2
    assert len(list_companies({"industry": ["互联网", "能源"]})) == 4
    assert len(list_companies({"industry": ["金融"]})) == 0


def test_filter_by_nature_single_unchanged(app_db):
    _add("字节跳动", nature="私企")
    _add("国家电网", nature="央企")
    _add("中石化", nature="国企")
    assert len(list_companies({"nature": "国企"})) == 1
    assert len(list_companies({"nature": "央企"})) == 1
    assert len(list_companies({"nature": "外企"})) == 0


def test_filter_by_keyword_name_like(app_db):
    _add("字节跳动")
    _add("字节跳动有限公司")
    _add("腾讯")
    assert len(list_companies({"keyword": "字节"})) == 2
    assert len(list_companies({"keyword": "腾讯"})) == 1


def test_filter_single_value_compat(app_db):
    """单值兼容旧调用：字符串直接传给 dao 仍按单个精确值匹配。"""
    _add("字节跳动", city="北京", industry="互联网")
    _add("腾讯", city="深圳", industry="互联网")
    assert len(list_companies({"city": "北京"})) == 1
    assert len(list_companies({"industry": "互联网"})) == 2
    assert len(list_companies({"city": "北"})) == 0  # 字符串同样精确匹配


def test_filter_combined(app_db):
    _add("字节跳动", industry="互联网", city="北京", nature="私企")
    _add("腾讯", industry="互联网", city="深圳", nature="私企")
    _add("国家电网", industry="能源", city="北京", nature="央企")
    # 多值（city/industry）+ 单值（nature）组合
    result = list_companies({"city": ["北京"], "industry": ["互联网"], "nature": "私企"})
    assert [c["name"] for c in result] == ["字节跳动"]
    assert len(list_companies({"city": ["北京"], "nature": "央企"})) == 1
    # 多值 city + keyword 组合
    assert [c["name"] for c in list_companies({"city": ["北京", "深圳"], "keyword": "腾讯"})] == ["腾讯"]
    # 多值 industry + nature 组合
    assert len(list_companies({"industry": ["互联网", "能源"], "nature": "央企"})) == 1


def test_filter_missing_values_not_matched(app_db):
    _add("未填城市公司", industry="互联网", nature=None)
    assert len(list_companies({"city": ["北京"]})) == 0
    assert len(list_companies({"nature": "国企"})) == 0


def test_processed_default_unprocessed(app_db):
    """新建公司默认未处理（processed=0），可显式传 1 创建为已处理。"""
    c1 = create_company({"name": "默认公司", "website": "https://x.com"})
    assert c1["processed"] == 0
    c2 = create_company({"name": "已处理公司", "website": "https://x.com", "processed": True})
    assert c2["processed"] == 1


def test_filter_by_processed(app_db):
    _add("甲", processed=0)
    _add("乙", processed=1)
    _add("丙", processed=1)
    assert len(list_companies({"processed": 1})) == 2
    assert len(list_companies({"processed": 0})) == 1
    assert len(list_companies({"processed": None})) == 3  # 不筛
    assert len(list_companies({})) == 3


def test_filter_processed_combined(app_db):
    _add("甲", city="北京", processed=0)
    _add("乙", city="北京", processed=1)
    _add("丙", city="深圳", processed=1)
    assert [c["name"] for c in list_companies({"city": ["北京"], "processed": 1})] == ["乙"]
    assert [c["name"] for c in list_companies({"processed": 0})] == ["甲"]


def test_update_processed(app_db):
    c = create_company({"name": "甲公司", "website": "https://x.com"})
    from app.dao import update_company
    updated = update_company(c["id"], {"processed": True})
    assert updated["processed"] == 1
    updated = update_company(c["id"], {"processed": False})
    assert updated["processed"] == 0
