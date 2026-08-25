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
    assert result["career_url"]


def test_resolve_mapping_hit_empty_career_url():
    result = resolve_mod.resolve_company("中国烟草")
    assert result["source"] == "mapping"
    assert result["website"] == "https://www.tobacco.gov.cn"
    assert result["career_url"] is None


def test_resolve_search_success(app_db, monkeypatch):
    monkeypatch.setattr(resolve_mod, "search_fallback",
                        lambda name, deadline=None: ("https://example.com", "互联网"))
    monkeypatch.setattr(resolve_mod, "probe_career_url",
                        lambda website, deadline=None: "https://example.com/careers")
    result = resolve_mod.resolve_company("某未知公司")
    assert result["source"] == "search"
    assert result["website"] == "https://example.com"
    assert result["industry"] == "互联网"
    assert result["career_url"] == "https://example.com/careers"


def test_resolve_search_failed(app_db, monkeypatch):
    monkeypatch.setattr(resolve_mod, "search_fallback",
                        lambda name, deadline=None: (None, None))
    result = resolve_mod.resolve_company("某未知公司")
    assert result["source"] == "failed"
    assert result["website"] is None
    assert result["industry"] is None
    assert result["career_url"] is None
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
                        lambda name, deadline=None: (None, None))
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
                        lambda name, deadline=None: (None, None))
    result = _run_resolve({"company_ids": [c1["id"], c2["id"]]}, None, {})
    assert result["resolved"] == 1
    assert [r["source"] for r in result["results"]] == ["mapping", "failed"]
