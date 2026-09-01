"""岗位状态体系重规划单测：迁移 006 合并「简历筛选」/ next_time / fail_stage / last_note 冗余列。"""
from contextlib import closing

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app import config, db
from app.dao import STATUS_ALL, change_status_tx, create_job, delete_job, get_job
from app.errors import APIError, error_body
from app.routes import router
from app.services import change_status, export_backup, import_backup


def _make_client():
    """仅挂业务路由 + 统一错误处理的最小测试应用（不含 token 鉴权中间件）。"""
    app = FastAPI()
    app.include_router(router, prefix="/api")

    @app.exception_handler(APIError)
    async def _api_error_handler(_: Request, exc: APIError):
        return JSONResponse(status_code=exc.status_code,
                            content=error_body(exc.code, exc.message, exc.details))

    return TestClient(app)


# ---------------- 迁移 006：合并「简历筛选」+ 新增 4 列 ----------------
def test_migration_006_merges_screening_status(tmp_path, monkeypatch):
    """单独 tmp 库先构建 001-005 版本（含 schema_migrations 记录），注入「简历筛选」岗位，
    再 db.migrate() 升级到 006：验证状态归一「已投递」且新列可用。"""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "old.db")
    scripts = db._load_scripts()
    # 1) 应用到 005 版本并记录迁移历史（模拟旧库）
    with closing(db.get_conn()) as conn:
        with conn:
            for version, name, sql in scripts:
                if version > 5:
                    break
                for stmt in sql.split(";"):
                    if stmt.strip():
                        conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, "2026-08-01T00:00:00"),
                )
    # 2) 旧库中注入「简历筛选」岗位（绕过新枚举直接写库）
    with closing(db.get_conn()) as conn:
        with conn:
            conn.execute(
                "INSERT INTO jobs (id, company, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                ("j-screening", "A公司", "简历筛选", "2026-08-01T00:00:00", "2026-08-01T00:00:00"),
            )
    # 3) 升级到最新版本（当前 007；断言 >=6 保证后续新增迁移不再破坏本用例）
    db.migrate()
    assert db.current_schema_version() >= 6
    job = get_job("j-screening")
    assert job["status"] == "已投递"  # 当前状态归一
    for col in ("next_time", "fail_stage", "last_note", "last_note_at"):
        assert col in job  # 新增列存在（旧行自然为 None）


def test_status_all_no_screening(app_db):
    """新枚举不含「简历筛选」，旧枚举流转到该状态应 400。"""
    assert "简历筛选" not in STATUS_ALL
    assert len(STATUS_ALL) == 9
    job = create_job({"company": "示例"})
    with pytest.raises(APIError) as e:
        change_status(job["id"], "简历筛选")
    assert e.value.status_code == 400


# ---------------- next_time：等待环节落库 / 离开自动清空 / 格式校验 ----------------
def test_next_time_set_on_wait_and_cleared_on_next(app_db):
    job = create_job({"company": "示例"})
    job, _ = change_status(job["id"], "笔试", next_time="2026-09-01T09:00")
    assert job["next_time"] == "2026-09-01T09:00"
    # 再流转到下一等待环节不带 next_time → 自动清空
    job, _ = change_status(job["id"], "一面")
    assert job["next_time"] is None


def test_next_time_date_only_accepted(app_db):
    job = create_job({"company": "示例"})
    job, _ = change_status(job["id"], "二面", next_time="2026-09-05")
    assert job["next_time"] == "2026-09-05"


def test_invalid_next_time_rejected(app_db):
    job = create_job({"company": "示例"})
    with pytest.raises(APIError) as e:
        change_status(job["id"], "笔试", next_time="abc")
    assert e.value.status_code == 400


def test_next_time_cleared_on_non_wait_status(app_db):
    """非等待态带 next_time → 结果为 NULL 不报错（离开等待环节自动清空）。"""
    job = create_job({"company": "示例"})
    job, _ = change_status(job["id"], "笔试", next_time="2026-09-01")
    job, _ = change_status(job["id"], "已投递", next_time="2026-09-05")
    assert job["next_time"] is None


# ---------------- fail_stage：被拒标签落库 / 重新推进清空 / 枚举校验 ----------------
def test_fail_stage_set_on_rejected_and_cleared(app_db):
    job = create_job({"company": "示例"})
    job, _ = change_status(job["id"], "笔试")
    job, _ = change_status(job["id"], "已拒绝", fail_stage="笔试挂")
    assert job["fail_stage"] == "笔试挂"
    # 从拒绝重新推进 → 标签清空
    job, _ = change_status(job["id"], "已投递")
    assert job["fail_stage"] is None


def test_invalid_fail_stage_rejected(app_db):
    job = create_job({"company": "示例"})
    with pytest.raises(APIError) as e:
        change_status(job["id"], "已拒绝", fail_stage="乱写的标签")
    assert e.value.status_code == 400


def test_fail_stage_cleared_on_non_rejected(app_db):
    """非拒绝态带 fail_stage → 结果为 NULL 不报错（重新推进自动清标签）。"""
    job = create_job({"company": "示例"})
    job, _ = change_status(job["id"], "已拒绝", fail_stage="一面挂")
    job, _ = change_status(job["id"], "一面", fail_stage="笔试挂")
    assert job["fail_stage"] is None


# ---------------- last_note / last_note_at：带备注刷新，空备注保留 ----------------
def test_last_note_updated_then_kept(app_db):
    job = create_job({"company": "示例"})
    job, _ = change_status(job["id"], "笔试", note="收到笔试邀请", time="2026-08-24T10:00:00")
    assert job["last_note"] == "收到笔试邀请"
    assert job["last_note_at"] == "2026-08-24T10:00:00"
    # 再流转不带 note → 冗余列保留原值不动
    job, _ = change_status(job["id"], "一面", time="2026-08-25T10:00:00")
    assert job["last_note"] == "收到笔试邀请"
    assert job["last_note_at"] == "2026-08-24T10:00:00"


# ---------------- 流转与 applied_at 回归 ----------------
def test_applied_at_logic_unaffected(app_db):
    job = create_job({"company": "示例"})
    job, _ = change_status(job["id"], "已投递", time="2026-08-24T10:00:00")
    assert job["applied_at"] == "2026-08-24"
    job, _ = change_status(job["id"], "笔试", time="2026-08-25T10:00:00")
    job, _ = change_status(job["id"], "已投递", time="2026-08-26T10:00:00")
    assert job["applied_at"] == "2026-08-24"  # 已投递不覆盖已有值


def test_change_status_tx_stores_new_columns(app_db):
    """事务层：新辅助列随 UPDATE 一并落库。"""
    job = create_job({"company": "示例"})
    change_status_tx(job["id"], "笔试", "待投递", "备注", "2026-08-24T10:00:00",
                     None, None, "2026-08-24T10:00:00",
                     next_time="2026-09-01", fail_stage=None,
                     last_note="备注", last_note_at="2026-08-24T10:00:00")
    row = get_job(job["id"])
    assert row["next_time"] == "2026-09-01"
    assert row["last_note"] == "备注" and row["last_note_at"] == "2026-08-24T10:00:00"


# ---------------- PUT 编辑 next_time / fail_stage ----------------
def test_put_updates_and_clears_next_time_fail_stage(app_db):
    client = _make_client()
    resp = client.post("/api/jobs", json={"company": "示例公司", "position": "后端开发"})
    assert resp.status_code == 201
    jid = resp.json()["id"]

    resp = client.put(f"/api/jobs/{jid}", json={"next_time": "2026-09-10T14:00", "fail_stage": "一面挂"})
    assert resp.status_code == 200
    assert resp.json()["next_time"] == "2026-09-10T14:00"
    assert resp.json()["fail_stage"] == "一面挂"

    # 显式传 null 清空
    resp = client.put(f"/api/jobs/{jid}", json={"next_time": None, "fail_stage": None})
    assert resp.status_code == 200
    assert resp.json()["next_time"] is None and resp.json()["fail_stage"] is None


def test_put_validates_next_time_and_fail_stage(app_db):
    client = _make_client()
    resp = client.post("/api/jobs", json={"company": "示例公司"})
    jid = resp.json()["id"]
    assert client.put(f"/api/jobs/{jid}", json={"next_time": "abc"}).status_code == 400
    assert client.put(f"/api/jobs/{jid}", json={"fail_stage": "乱写"}).status_code == 400


def test_put_does_not_override_when_absent(app_db):
    """PUT 未带 next_time/fail_stage 时原值保留（exclude_unset 语义）。"""
    client = _make_client()
    resp = client.post("/api/jobs", json={"company": "示例公司"})
    jid = resp.json()["id"]
    client.put(f"/api/jobs/{jid}", json={"next_time": "2026-09-10", "fail_stage": "简历挂"})
    resp = client.put(f"/api/jobs/{jid}", json={"position": "全栈"})
    assert resp.status_code == 200
    assert resp.json()["next_time"] == "2026-09-10"
    assert resp.json()["fail_stage"] == "简历挂"


# ---------------- 备份：新字段导出 / 导入还原 ----------------
def test_backup_export_includes_new_fields(app_db):
    job = create_job({"company": "示例"})
    change_status(job["id"], "笔试", note="笔试通知", next_time="2026-09-01T09:00",
                  time="2026-08-24T10:00:00")
    job, _ = change_status(job["id"], "已拒绝", fail_stage="笔试挂", time="2026-08-25T10:00:00")
    backup = export_backup()
    item = next(x for x in backup["jobs"] if x["id"] == job["id"])
    assert item["fail_stage"] == "笔试挂"       # 拒绝态标签已落库
    assert item["next_time"] is None            # 非等待态自动清空
    assert item["last_note"] == "笔试通知"       # 最近备注冗余列
    assert item["last_note_at"] == "2026-08-24T10:00:00"


def test_backup_import_restores_new_fields(app_db):
    job = create_job({"company": "示例"})
    change_status(job["id"], "笔试", note="笔试通知", next_time="2026-09-01T09:00",
                  time="2026-08-24T10:00:00")
    job, _ = change_status(job["id"], "已拒绝", fail_stage="笔试挂", time="2026-08-25T10:00:00")
    backup = export_backup()
    delete_job(job["id"])
    assert get_job(job["id"]) is None

    res = import_backup({"schema_version": 1, "mode": "merge",
                         "jobs": backup["jobs"], "companies": backup["companies"],
                         "resumes": backup["resumes"]})
    assert res["jobs_added"] == 1
    restored = get_job(job["id"])
    assert restored["fail_stage"] == "笔试挂"
    assert restored["last_note"] == "笔试通知"
    assert restored["last_note_at"] == "2026-08-24T10:00:00"


def test_backup_old_backup_without_new_fields_imports(app_db):
    """旧备份无新字段 → 导入后自然为 None，不报错。"""
    res = import_backup({"schema_version": 1, "mode": "overwrite",
                         "jobs": [{"id": "j-old", "company": "B公司", "position": "旧岗位"}],
                         "companies": [{"id": "c1", "name": "B公司", "website": "https://b.com"}],
                         "resumes": []})
    assert res["jobs_added"] == 1
    row = get_job("j-old")
    for col in ("next_time", "fail_stage", "last_note", "last_note_at"):
        assert row[col] is None
