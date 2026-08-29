"""编辑岗位设置投递时间：POST 创建带 applied_at / PUT 修改 / GET 校验 / exclude_unset 不覆盖。"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.errors import APIError, error_body
from app.routes import router


def _make_client():
    """仅挂业务路由 + 统一错误处理的最小测试应用（不含 token 鉴权中间件）。"""
    app = FastAPI()
    app.include_router(router, prefix="/api")

    @app.exception_handler(APIError)
    async def _api_error_handler(_: Request, exc: APIError):
        return JSONResponse(status_code=exc.status_code,
                            content=error_body(exc.code, exc.message, exc.details))

    return TestClient(app)


def test_job_applied_at_through_update_chain(app_db):
    """POST 创建带 applied_at → PUT 修改 applied_at → GET 校验生效。"""
    client = _make_client()

    # 1) POST /api/jobs 带 applied_at 创建
    resp = client.post("/api/jobs", json={
        "company": "示例公司", "position": "后端开发", "applied_at": "2026-08-20",
    })
    assert resp.status_code == 201
    jid = resp.json()["id"]
    assert resp.json()["applied_at"] == "2026-08-20"

    # 2) PUT /api/jobs/{id} 修改 applied_at
    resp = client.put(f"/api/jobs/{jid}", json={"applied_at": "2026-08-25"})
    assert resp.status_code == 200
    assert resp.json()["applied_at"] == "2026-08-25"

    # 3) GET /api/jobs/{id} 校验生效
    resp = client.get(f"/api/jobs/{jid}")
    assert resp.status_code == 200
    assert resp.json()["applied_at"] == "2026-08-25"


def test_put_without_applied_at_keeps_existing(app_db):
    """PUT 未带 applied_at 时原值不被覆盖（exclude_unset 语义）。"""
    client = _make_client()

    resp = client.post("/api/jobs", json={
        "company": "示例公司", "position": "前端开发", "applied_at": "2026-08-20",
    })
    jid = resp.json()["id"]

    # 仅更新 position，不带 applied_at
    resp = client.put(f"/api/jobs/{jid}", json={"position": "全栈开发"})
    assert resp.status_code == 200
    assert resp.json()["position"] == "全栈开发"
    assert resp.json()["applied_at"] == "2026-08-20"  # 原值保留

    # 显式传 null 才可清空
    resp = client.put(f"/api/jobs/{jid}", json={"applied_at": None})
    assert resp.status_code == 200
    assert resp.json()["applied_at"] is None


def test_job_create_without_applied_at_is_none(app_db):
    """新建岗位不传 applied_at 时保持 None（可随后由状态流转写入）。"""
    client = _make_client()
    resp = client.post("/api/jobs", json={"company": "示例公司"})
    assert resp.status_code == 201
    assert resp.json()["applied_at"] is None
