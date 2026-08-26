"""按公司名称自动补全单测（PRD 4.12 v0.6）：映射命中 + 搜索兜底（mock）+ 失败路径。

搜索兜底与探测通过 monkeypatch 注入，不访问真实搜索引擎。
"""
from app import dao
from app.fetcher import resolve as resolve_mod
from app.fetcher.tasks import _run_resolve
from app.services import resolve_company_by_name, resolve_company_for_id


# ---------------- resolve_company（核心补全逻辑） ----------------

def test_resolve_mapping_hit():
    result = resolve_mod.resolve_company("字节跳动")
    assert result["source"] == "mapping"
    assert result["website"] == "https://www.bytedance.com"
    assert result["industry"] == "互联网"
    assert result["city"] == "北京"
    assert result["nature"] == "私企"
    assert result["career_url"]


def test_resolve_mapping_hit_empty_career_url():
    result = resolve_mod.resolve_company("中国烟草")
    assert result["source"] == "mapping"
    assert result["website"] == "https://www.tobacco.gov.cn"
    assert result["career_url"] is None
    assert result["city"] == "北京"
    assert result["nature"] == "央企"


def test_resolve_search_success(app_db, monkeypatch):
    monkeypatch.setattr(resolve_mod, "search_fallback",
                        lambda name, deadline=None: {
                            "website": "https://example.com", "industry": "互联网",
                            "confidence": "high", "snippet": "某未知公司 官网",
                            "homepage": "某未知公司总部位于北京，是一家民营企业，专注互联网服务"})
    monkeypatch.setattr(resolve_mod, "probe_career_url",
                        lambda website, deadline=None: "https://example.com/careers")
    result = resolve_mod.resolve_company("某未知公司")
    assert result["source"] == "search"
    assert result["website"] == "https://example.com"
    assert result["industry"] == "互联网"
    assert result["career_url"] == "https://example.com/careers"
    assert result["confidence"] == "high"
    # 搜索路径也能尽力提取城市/性质（来自摘要/官网文本）
    assert result["city"] == "北京"
    assert result["nature"] == "私企"


def test_resolve_search_failed(app_db, monkeypatch):
    monkeypatch.setattr(resolve_mod, "search_fallback",
                        lambda name, deadline=None: {"website": None, "industry": None,
                                                     "confidence": None, "snippet": None,
                                                     "homepage": None})
    result = resolve_mod.resolve_company("某未知公司")
    assert result["source"] == "failed"
    assert result["website"] is None
    assert result["industry"] is None
    assert result["career_url"] is None
    assert result["city"] is None and result["nature"] is None
    assert result["error"]


def test_resolve_blank_name():
    result = resolve_mod.resolve_company("  ")
    assert result["source"] == "failed"
    assert result["error"]


# ---------------- 端点服务（POST /api/companies/resolve、{id}/resolve） ----------------

def test_resolve_endpoint_mapping_hit(app_db):
    result = resolve_company_by_name("腾讯")
    assert result["source"] == "mapping"
    assert result["website"] == "https://www.tencent.com"


def test_resolve_endpoint_search_failed(app_db, monkeypatch):
    monkeypatch.setattr(resolve_mod, "search_fallback",
                        lambda name, deadline=None: {"website": None, "industry": None,
                                                     "confidence": None, "snippet": None,
                                                     "homepage": None})
    result = resolve_company_by_name("某未知公司")
    assert result["source"] == "failed"
    assert result["error"]


def test_resolve_existing_company_mapping(app_db):
    company = dao.create_company({"name": "美团", "website": ""})
    result = resolve_company_for_id(company["id"])
    assert result["company_id"] == company["id"]
    assert result["source"] == "mapping"
    assert result["website"] == "https://www.meituan.com"


def test_resolve_existing_company_not_found(app_db):
    from app.errors import APIError
    import pytest
    with pytest.raises(APIError) as exc_info:
        resolve_company_for_id("no-such-id")
    assert exc_info.value.code == "NOT_FOUND"


# ---------------- 异步批量补全任务（复用 tasks.py） ----------------

def test_run_resolve_task_mapping_only(app_db):
    c1 = dao.create_company({"name": "美团", "website": ""})
    c2 = dao.create_company({"name": "快手", "website": ""})
    task = {"progress": "", "status": "running"}
    result = _run_resolve({"company_ids": [c1["id"], c2["id"]]}, None, task)
    assert result["total"] == 2 and result["resolved"] == 2
    assert all(r["source"] == "mapping" for r in result["results"])
    assert task["progress"] == "已补全 2/2"


def test_run_resolve_task_missing_company(app_db):
    result = _run_resolve({"company_ids": ["no-such-id"]}, None, {})
    assert result["resolved"] == 0
    assert result["results"][0]["error"] == "公司不存在"


def test_run_resolve_task_partial_failure(app_db, monkeypatch):
    c1 = dao.create_company({"name": "腾讯", "website": ""})   # 映射命中
    c2 = dao.create_company({"name": "某未知公司", "website": ""})  # 搜索失败
    monkeypatch.setattr(resolve_mod, "search_fallback",
                        lambda name, deadline=None: {"website": None, "industry": None,
                                                     "confidence": None, "snippet": None,
                                                     "homepage": None})
    result = _run_resolve({"company_ids": [c1["id"], c2["id"]]}, None, {})
    assert result["resolved"] == 1
    assert [r["source"] for r in result["results"]] == ["mapping", "failed"]


def test_run_resolve_task_writes_city_nature(app_db):
    c = dao.create_company({"name": "字节跳动", "website": ""})
    result = _run_resolve({"company_ids": [c["id"]]}, None, {})
    assert result["resolved"] == 1 and result["results"][0]["source"] == "mapping"
    updated = dao.get_company(c["id"])
    assert updated["city"] == "北京"
    assert updated["nature"] == "私企"
    assert updated["website"] == "https://www.bytedance.com"


def test_run_resolve_task_skips_complete_company(app_db):
    c = dao.create_company({"name": "腾讯", "website": "https://www.tencent.com",
                            "industry": "互联网", "city": "深圳", "nature": "私企",
                            "career_url": "https://careers.tencent.com/"})
    result = _run_resolve({"company_ids": [c["id"]]}, None, {})
    assert result["skipped"] == 1 and result["resolved"] == 0
    assert result["results"][0]["source"] == "skipped"


def test_run_resolve_task_skips_search_sourced_missing_city_nature(app_db, monkeypatch):
    """非映射公司：主体信息完整、仅缺城市/性质 → 直接跳过，不触发搜索。"""
    c = dao.create_company({"name": "某未知公司", "website": "https://example.com",
                            "industry": "互联网", "career_url": "https://example.com/careers"})
    calls = []
    monkeypatch.setattr(resolve_mod, "search_fallback",
                        lambda name, deadline=None: calls.append(name) or {
                            "website": "https://x.com", "industry": "科技", "confidence": "high",
                            "snippet": None, "homepage": None})
    result = _run_resolve({"company_ids": [c["id"]]}, None, {})
    assert calls == []  # 未发起网络搜索
    assert result["results"][0]["source"] == "skipped"
    assert result["skipped"] == 1


def test_run_resolve_task_fills_city_nature_for_mapping_with_complete_main(app_db):
    """映射公司：主体信息完整、仅缺城市/性质 → 映射命中瞬间补齐，不触发搜索。"""
    c = dao.create_company({"name": "美团", "website": "https://www.meituan.com",
                            "industry": "互联网", "career_url": "https://zhaopin.meituan.com/"})
    result = _run_resolve({"company_ids": [c["id"]]}, None, {})
    assert result["results"][0]["source"] == "mapping"
    updated = dao.get_company(c["id"])
    assert updated["city"] == "北京" and updated["nature"] == "私企"


# ---------------- 央企国企名录（guoyang-pro 合并条目，缺官网） ----------------

def test_resolve_roster_soe_without_website_merges_metadata(app_db, monkeypatch):
    """名录公司缺官网：搜索补官网，行业/城市/性质以名录为准（source 仍标 search 供核对）。"""
    monkeypatch.setattr(resolve_mod, "search_fallback",
                        lambda name, deadline=None: {
                            "website": "https://www.cnooc.com.cn", "industry": None,
                            "confidence": "high", "snippet": "中国海洋石油集团有限公司 官网",
                            "homepage": None})
    monkeypatch.setattr(resolve_mod, "probe_career_url", lambda website, deadline=None: None)
    result = resolve_mod.resolve_company("中海油")
    assert result["source"] == "search"
    assert result["website"] == "https://www.cnooc.com.cn"
    assert result["industry"] == "能源"  # 名录元数据（搜索返回 None）
    assert result["city"] == "北京"
    assert result["nature"] == "央企"
    assert result["confidence"] == "high"


def test_resolve_roster_soe_when_search_fails_returns_metadata(app_db, monkeypatch):
    """名录公司搜索也失败 → 返回名录元数据（官网留空待人工）。"""
    monkeypatch.setattr(resolve_mod, "search_fallback",
                        lambda name, deadline=None: {"website": None, "industry": None,
                                                     "confidence": None, "snippet": None,
                                                     "homepage": None})
    result = resolve_mod.resolve_company("上海烟草")
    assert result["source"] == "mapping"
    assert result["website"] is None
    assert result["nature"] == "央企" and result["city"] == "上海"


def test_run_resolve_task_roster_soe_searches_website(app_db, monkeypatch):
    """批量补全名录公司：搜索补官网并写入名录元数据。"""
    c = dao.create_company({"name": "中海油", "website": ""})
    monkeypatch.setattr(resolve_mod, "search_fallback",
                        lambda name, deadline=None: {
                            "website": "https://www.cnooc.com.cn", "industry": None,
                            "confidence": "high", "snippet": "中国海洋石油集团 官网",
                            "homepage": None})
    monkeypatch.setattr(resolve_mod, "probe_career_url", lambda website, deadline=None: None)
    result = _run_resolve({"company_ids": [c["id"]]}, None, {})
    assert result["results"][0]["source"] == "search"
    updated = dao.get_company(c["id"])
    assert updated["website"] == "https://www.cnooc.com.cn"
    assert updated["nature"] == "央企" and updated["city"] == "北京" and updated["industry"] == "能源"


# ---------------- A股离线库 / ICP 备案 中间层 ----------------

def test_resolve_company_info_tier(app_db, monkeypatch):
    """未命中映射但命中 A股离线库 → 直接返回官网/行业/城市（离线，不发搜索）。"""
    from app.fetcher import company_info
    company_info._INDEX = {"平安银行": {"name": "平安银行", "website": "https://bank.pingan.com",
                                       "industry": "金融", "city": "深圳", "nature": None}}

    def boom(name, deadline=None):
        raise AssertionError("不应触发搜索")

    monkeypatch.setattr(resolve_mod, "search_fallback", boom)
    result = resolve_mod.resolve_company("平安银行股份有限公司")
    assert result["source"] == "info"
    assert result["website"] == "https://bank.pingan.com"
    assert result["industry"] == "金融" and result["city"] == "深圳"
    assert result["nature"] is None and result["career_url"] is None


def test_resolve_company_icp_tier(app_db, monkeypatch):
    """未命中映射/离线库但配置了 ICP 服务 → 用备案域名，不发搜索。"""
    monkeypatch.setenv("ICP_API_URL", "http://127.0.0.1:8080")
    monkeypatch.setattr("app.fetcher.icp.fetch_json",
                        lambda url, deadline=None: {"data": {"company_name": "某中小企业", "domain": "moucompany.com"}})

    def boom(name, deadline=None):
        raise AssertionError("不应触发搜索")

    monkeypatch.setattr(resolve_mod, "search_fallback", boom)
    result = resolve_mod.resolve_company("某中小企业")
    assert result["source"] == "icp"
    assert result["website"] == "https://moucompany.com"
    assert result["confidence"] == "high"
