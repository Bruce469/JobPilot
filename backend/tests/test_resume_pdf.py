"""简历源 PDF 附件单测：上传校验 / 在线预览 / 删除清理 / 备份字段。"""
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app import config
from app.dao import delete_resume, get_resume
from app.errors import APIError, error_body
from app.routes import router
from app.services import create_resume_with_pdf, export_backup, import_backup

# 最小合法 PDF 字节（以 %PDF- 魔数开头即可，不要求可渲染）
FAKE_PDF = b"%PDF-1.4 fake pdf body"


def _make_client():
    """仅挂业务路由 + 统一错误处理的最小测试应用（不含 token 鉴权中间件）。"""
    app = FastAPI()
    app.include_router(router, prefix="/api")

    @app.exception_handler(APIError)
    async def _api_error_handler(_: Request, exc: APIError):
        return JSONResponse(status_code=exc.status_code,
                            content=error_body(exc.code, exc.message, exc.details))

    return TestClient(app)


def _upload(client, name="张三的简历.pdf", content=FAKE_PDF):
    return client.post("/api/resumes/upload-pdf",
                       files={"file": (name, content, "application/pdf")})


# ---------------- 上传 ----------------
def test_upload_pdf_success(app_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESUME_FILES_DIR", tmp_path / "resume_files")
    client = _make_client()

    resp = _upload(client)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "张三的简历"                      # 文件名去扩展名、去空白
    assert data["pdf_file"] == f"{data['id']}.pdf"          # 存文件名（不含路径）
    assert data["basic"]["name"] == "张三的简历"             # 默认结构 basic 空字段
    path = config.RESUME_FILES_DIR / data["pdf_file"]
    assert path.is_file() and path.read_bytes() == FAKE_PDF  # 磁盘文件已写入

    # 在线预览：200 + application/pdf + 字节一致
    resp2 = client.get(f"/api/resumes/{data['id']}/pdf")
    assert resp2.status_code == 200
    assert resp2.headers["content-type"] == "application/pdf"
    assert resp2.content == FAKE_PDF


def test_upload_pdf_empty_name_default(app_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESUME_FILES_DIR", tmp_path / "resume_files")
    client = _make_client()
    resp = _upload(client, name=".pdf")
    assert resp.status_code == 201
    assert resp.json()["name"] == "未命名简历"


def test_upload_rejects_non_pdf_extension(app_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESUME_FILES_DIR", tmp_path / "resume_files")
    client = _make_client()
    resp = _upload(client, name="简历.docx")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_rejects_bad_magic(app_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESUME_FILES_DIR", tmp_path / "resume_files")
    client = _make_client()
    resp = _upload(client, content=b"not a pdf at all")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_rejects_oversize(app_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESUME_FILES_DIR", tmp_path / "resume_files")
    # 服务层直接校验大小上限（构造略超 10MB 的 bytes，不落盘）
    with pytest.raises(APIError) as exc_info:
        create_resume_with_pdf("big.pdf", b"%PDF-1.4" + b"x" * (10 * 1024 * 1024))
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert not (config.RESUME_FILES_DIR / "big.pdf").exists()


def test_upload_rejects_oversize_via_route(app_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESUME_FILES_DIR", tmp_path / "resume_files")
    client = _make_client()
    resp = _upload(client, content=b"%PDF-1.4" + b"x" * (10 * 1024 * 1024 + 1))
    assert resp.status_code == 400


# ---------------- 在线预览 404 ----------------
def test_get_pdf_resume_not_found(app_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESUME_FILES_DIR", tmp_path / "resume_files")
    client = _make_client()
    resp = client.get("/api/resumes/nonexistent/pdf")
    assert resp.status_code == 404


def test_get_pdf_no_attachment(app_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESUME_FILES_DIR", tmp_path / "resume_files")
    client = _make_client()
    created = _upload(client).json()
    # 清掉 pdf_file 模拟无附件的简历
    from app.services import update_resume
    update_resume(created["id"], {"pdf_file": None})
    resp = client.get(f"/api/resumes/{created['id']}/pdf")
    assert resp.status_code == 404
    assert resp.json()["error"]["message"] == "该简历没有源 PDF 文件"


# ---------------- 删除清理 ----------------
def test_delete_resume_removes_disk_file(app_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESUME_FILES_DIR", tmp_path / "resume_files")
    client = _make_client()
    rid = _upload(client).json()["id"]
    path = config.RESUME_FILES_DIR / f"{rid}.pdf"
    assert path.exists()
    resp = client.delete(f"/api/resumes/{rid}")
    assert resp.status_code == 204
    assert get_resume(rid) is None
    assert not path.exists()  # 磁盘附件一并清理


def test_delete_resume_no_pdf_file_still_ok(app_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESUME_FILES_DIR", tmp_path / "resume_files")
    client = _make_client()
    rid = _upload(client).json()["id"]
    path = config.RESUME_FILES_DIR / f"{rid}.pdf"
    path.unlink()  # 模拟磁盘附件已丢失
    delete_resume(rid)  # 删除记录时附件清理应 best-effort 跳过，不抛错
    assert get_resume(rid) is None
    assert not path.exists()


# ---------------- 备份导出 / 导入 ----------------
def test_backup_export_includes_pdf_file_and_import_restores(app_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESUME_FILES_DIR", tmp_path / "resume_files")
    client = _make_client()
    data = _upload(client).json()
    backup = export_backup()
    item = next(x for x in backup["resumes"] if x["id"] == data["id"])
    assert item["pdf_file"] == f"{data['id']}.pdf"  # 导出含 pdf_file（文件名）

    # 删除本机记录后 merge 导入，pdf_file 一并还原（文件本体不在 JSON 备份内，属已知限制）
    delete_resume(data["id"])
    assert get_resume(data["id"]) is None
    res = import_backup({"schema_version": 1, "mode": "merge",
                         "jobs": [], "companies": [], "resumes": backup["resumes"]})
    assert res["resumes_added"] == 1
    assert get_resume(data["id"])["pdf_file"] == item["pdf_file"]
