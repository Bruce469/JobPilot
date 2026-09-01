"""公司库 facets 单测：cities/industries/natures 三列 DISTINCT 去重、忽略空值、按值排序。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dao import company_facets, create_company
from app.routes import router


def _add(name: str, **kw):
    create_company({"name": name, "website": "https://x.com", **kw})


def test_facets_empty_db(app_db):
    assert company_facets() == {"cities": [], "industries": [], "natures": []}


def test_facets_distinct_sorted(app_db):
    """多公司去重 + 按值升序（SQLite 按 Unicode 码点排序）。"""
    _add("字节跳动", city="北京", industry="互联网", nature="私企")
    _add("国家电网", city="北京", industry="能源", nature="国企")
    _add("腾讯", city="深圳", industry="互联网", nature="私企")
    result = company_facets()
    assert result["cities"] == ["北京", "深圳"]
    assert result["industries"] == ["互联网", "能源"]
    assert result["natures"] == ["国企", "私企"]


def test_facets_ignore_null_and_empty(app_db):
    """NULL / 空串 值不进入候选池。"""
    _add("空值公司", city=None, industry="", nature=None)
    _add("正常公司", city="北京", industry="互联网", nature="私企")
    result = company_facets()
    assert result["cities"] == ["北京"]
    assert result["industries"] == ["互联网"]
    assert result["natures"] == ["私企"]


def test_facets_route_smoke(app_db):
    """GET /api/companies/facets 返回候选池；静态路由不被 /companies/{company_id} 抢占。"""
    _add("字节跳动", city="北京", industry="互联网", nature="私企")
    _add("腾讯", city="深圳", industry="互联网", nature="私企")
    client = TestClient(_make_app())
    resp = client.get("/api/companies/facets")
    assert resp.status_code == 200
    assert resp.json() == {
        "cities": ["北京", "深圳"],
        "industries": ["互联网"],
        "natures": ["私企"],
    }
    # 顺带验证多值路由参数：逗号分隔拆分 + 精确命中
    resp = client.get("/api/companies/facets/")
    assert resp.status_code == 200
    resp = client.get("/api/companies", params={"city": "北京,深圳", "nature": "私企"})
    assert resp.status_code == 200
    # 同秒创建时 id 排序不定，按名称集合断言命中
    assert {c["name"] for c in resp.json()["items"]} == {"腾讯", "字节跳动"}


def _make_app():
    """仅挂业务路由的最小测试应用（与 test_job_applied_at 同构）。"""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app
