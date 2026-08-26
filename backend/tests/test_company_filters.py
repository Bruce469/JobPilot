"""公司库筛选单测：list_companies 按 city/industry/nature/keyword 组合过滤。"""
from app.dao import create_company, list_companies


def _add(name: str, **kw):
    create_company({"name": name, "website": "https://x.com", **kw})


def test_list_companies_no_filter_returns_all(app_db):
    _add("字节跳动", industry="互联网", city="北京", nature="私企", created_at="2026-01-01T00:00:00")
    _add("国家电网", industry="能源", city="北京", nature="央企", created_at="2026-01-02T00:00:00")
    _add("腾讯", industry="互联网", city="深圳", nature="私企", created_at="2026-01-03T00:00:00")
    assert len(list_companies()) == 3
    assert list_companies()[0]["name"] == "腾讯"  # created_at DESC 序


def test_filter_by_city_like(app_db):
    _add("字节跳动", city="北京")
    _add("国家电网", city="北京")
    _add("腾讯", city="深圳")
    assert len(list_companies({"city": "北"})) == 2
    assert len(list_companies({"city": "深圳"})) == 1
    assert len(list_companies({"city": "上海"})) == 0


def test_filter_by_industry_exact(app_db):
    _add("字节跳动", industry="互联网")
    _add("国家电网", industry="能源")
    _add("腾讯", industry="互联网")
    assert len(list_companies({"industry": "互联网"})) == 2
    assert len(list_companies({"industry": "能源"})) == 1


def test_filter_by_nature_exact(app_db):
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


def test_filter_combined(app_db):
    _add("字节跳动", industry="互联网", city="北京", nature="私企")
    _add("腾讯", industry="互联网", city="深圳", nature="私企")
    _add("国家电网", industry="能源", city="北京", nature="央企")
    result = list_companies({"city": "北京", "industry": "互联网", "nature": "私企"})
    assert [c["name"] for c in result] == ["字节跳动"]
    assert len(list_companies({"city": "北京", "nature": "央企"})) == 1


def test_filter_missing_values_not_matched(app_db):
    _add("未填城市公司", industry="互联网", nature=None)
    assert len(list_companies({"city": "北京"})) == 0
    assert len(list_companies({"nature": "国企"})) == 0
