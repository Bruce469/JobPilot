"""公司岗位关联单测：GET /api/companies/{id}/jobs 展开列表 + list_companies 附带 job_count。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dao import create_company, create_job, list_companies
from app.routes import router


def _make_app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


def test_list_companies_includes_job_count(app_db):
    c1 = create_company({"name": "甲公司", "website": "https://a.example.com"})
    c2 = create_company({"name": "乙公司", "website": "https://b.example.com"})
    create_job({"company": "甲公司", "company_id": c1["id"], "position": "后端"})
    create_job({"company": "甲公司", "company_id": c1["id"], "position": "前端"})
    create_job({"company": "乙公司", "company_id": c2["id"], "position": "测试"})
    create_job({"company": "未关联公司岗位", "position": "自由岗"})  # 无 company_id 不计数

    by_name = {c["name"]: c for c in list_companies()}
    assert by_name["甲公司"]["job_count"] == 2
    assert by_name["乙公司"]["job_count"] == 1
    assert "未关联公司岗位" not in by_name
    # 带筛选时 job_count 依旧正确（计数不随筛选变化）
    filtered = {c["name"]: c for c in list_companies({"keyword": "甲"})}
    assert filtered["甲公司"]["job_count"] == 2


def test_company_jobs_route(app_db):
    c = create_company({"name": "甲公司", "website": "https://a.example.com"})
    j1 = create_job({"company": "甲公司", "company_id": c["id"], "position": "后端开发"})
    j2 = create_job({"company": "甲公司", "company_id": c["id"], "position": "前端开发"})
    client = TestClient(_make_app())
    resp = client.get(f"/api/companies/{c['id']}/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert {j["position"] for j in data["items"]} == {"后端开发", "前端开发"}
    assert data["items"][0]["company_id"] == c["id"]
    assert {j["id"] for j in data["items"]} == {j1["id"], j2["id"]}


def test_company_jobs_missing_company(app_db):
    """公司不存在抛 404 APIError（路由 200 路径已由上面用例覆盖）。"""
    import pytest
    from app.errors import APIError
    from app import services
    with pytest.raises(APIError) as exc_info:
        services.list_company_jobs("no-such-id")
    assert exc_info.value.status_code == 404


def test_company_jobs_empty(app_db):
    c = create_company({"name": "无岗位公司", "website": "https://x.com"})
    client = TestClient(_make_app())
    resp = client.get(f"/api/companies/{c['id']}/jobs")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


def test_company_jobs_route_not_shadowed_by_get(app_db):
    """静态 facets 与公司级 jobs 路由不被 /companies/{company_id} 抢占。"""
    c = create_company({"name": "甲公司", "website": "https://a.example.com"})
    client = TestClient(_make_app())
    resp = client.get(f"/api/companies/{c['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "甲公司"
