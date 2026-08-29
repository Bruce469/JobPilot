"""DAO 层：四张表的增删改查，全部参数化 SQL（防注入），每操作短连接 + 事务提交。"""
import json
import sqlite3
from contextlib import closing

from . import util
from .db import get_conn

# 状态全集与终态（架构 4.1 / PRD 4.2；「简历筛选」已合并进「已投递」，见迁移 006）
STATUS_ALL = ["待投递", "已投递", "笔试", "一面", "二面", "三面/HR面", "已Offer", "已拒绝", "已放弃"]
TERMINAL = {"已Offer", "已拒绝", "已放弃"}
# 等待环节：next_time 计划时间仅在这些状态下有意义，离开即自动清空
WAIT_STATUSES = {"笔试", "一面", "二面", "三面/HR面"}
# 被拒环节标签：仅「已拒绝」状态下有意义，重新推进即自动清空
FAIL_STAGES = ["简历挂", "笔试挂", "一面挂", "二面挂", "三面挂", "HR挂", "其他"]

JOB_COLS = (
    "id", "company", "company_id", "position", "job_type", "degree", "city", "industry",
    "channel", "job_url", "source_job_id", "publish_date", "deadline", "applied_at",
    "status", "ended_at", "next_time", "fail_stage", "last_note", "last_note_at",
    "resume_id", "resume_name", "notes", "created_at", "updated_at",
)
COMPANY_COLS = (
    "id", "name", "website", "career_url", "industry", "city", "nature",
    "probe_status", "ats_type", "notes", "last_fetched_at", "last_fetch_result",
    "created_at",
)
RESUME_COLS = (
    "id", "name", "basic", "education", "experience", "projects", "skills",
    "summary", "pdf_file", "created_at", "updated_at",
)
SORT_WHITELIST = {"updated_at", "created_at", "deadline", "applied_at", "company", "status", "position"}


# ---------------- 行 → dict 解析 ----------------
def _job_from_row(row):
    d = dict(row)
    try:
        d["notes"] = json.loads(d["notes"]) if d.get("notes") else []
    except (TypeError, ValueError):
        d["notes"] = []
    return d


def _resume_from_row(row):
    d = dict(row)
    for key in ("basic", "education", "experience", "projects", "skills"):
        try:
            d[key] = json.loads(d[key]) if d.get(key) else ({} if key == "basic" else [])
        except (TypeError, ValueError):
            d[key] = {} if key == "basic" else []
    return d


def _dump(v):
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v


# ---------------- jobs ----------------
def get_job(jid):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (jid,)).fetchone()
    return _job_from_row(row) if row else None


def list_jobs(filters: dict) -> tuple[list, int]:
    conds, params = [], []
    statuses = filters.get("status")
    if statuses:
        conds.append(f"status IN ({','.join('?' * len(statuses))})")
        params.extend(statuses)
    elif not filters.get("include_ended"):
        conds.append(f"status NOT IN ({','.join('?' * len(TERMINAL))})")
        params.extend(TERMINAL)
    for col in ("company", "city"):
        if filters.get(col):
            conds.append(f"{col} LIKE ?")
            params.append(f"%{filters[col]}%")
    for col in ("industry", "channel"):
        if filters.get(col):
            conds.append(f"{col} = ?")
            params.append(filters[col])
    if filters.get("keyword"):
        kw = f"%{filters['keyword']}%"
        conds.append("(company LIKE ? OR position LIKE ?)")
        params.extend([kw, kw])
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    sort = filters.get("sort") or "updated_at"
    if sort not in SORT_WHITELIST:
        sort = "updated_at"
    direction = "ASC" if str(filters.get("sort_dir", "")).lower() == "asc" else "DESC"
    with closing(get_conn()) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM jobs {where}", params).fetchone()[0]
        # 空值（如 deadline/applied_at 未填）统一排最后，不随方向颠倒
        rows = conn.execute(
            f"SELECT * FROM jobs {where} ORDER BY ({sort} IS NULL), {sort} {direction}, id", params
        ).fetchall()
    return [_job_from_row(r) for r in rows], total


def all_jobs():
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at").fetchall()
    return [_job_from_row(r) for r in rows]


def create_job(data: dict) -> dict:
    now = util.now_iso()
    jid = data.get("id") or util.new_id()
    row = {c: None for c in JOB_COLS}
    row.update({
        "id": jid, "company": data.get("company"), "company_id": data.get("company_id"),
        "position": data.get("position"), "job_type": data.get("job_type"),
        "degree": data.get("degree"), "city": data.get("city"), "industry": data.get("industry"),
        "channel": data.get("channel"), "job_url": data.get("job_url"),
        "source_job_id": data.get("source_job_id"), "publish_date": data.get("publish_date"),
        "deadline": data.get("deadline"), "applied_at": data.get("applied_at"),
        "status": data.get("status") or "待投递", "ended_at": data.get("ended_at"),
        "next_time": data.get("next_time"), "fail_stage": data.get("fail_stage"),
        "last_note": data.get("last_note"), "last_note_at": data.get("last_note_at"),
        "resume_id": data.get("resume_id"), "resume_name": data.get("resume_name"),
        "notes": _dump(data.get("notes") or []),
        "created_at": data.get("created_at") or now, "updated_at": data.get("updated_at") or now,
    })
    cols = ", ".join(JOB_COLS)
    marks = ", ".join("?" * len(JOB_COLS))
    with closing(get_conn()) as conn:
        with conn:
            conn.execute(f"INSERT INTO jobs ({cols}) VALUES ({marks})", [row[c] for c in JOB_COLS])
    return get_job(jid)


def update_job(jid: str, fields: dict) -> dict:
    sets, params = [], []
    fields = dict(fields)
    fields.setdefault("updated_at", util.now_iso())
    for key, val in fields.items():
        if key not in JOB_COLS or key == "id":
            continue
        sets.append(f"{key} = ?")
        params.append(_dump(val))
    if sets:
        params.append(jid)
        with closing(get_conn()) as conn:
            with conn:
                conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", params)
    return get_job(jid)


def delete_job(jid: str) -> None:
    with closing(get_conn()) as conn:
        with conn:
            conn.execute("DELETE FROM jobs WHERE id = ?", (jid,))


def batch_delete(ids: list) -> int:
    if not ids:
        return 0
    marks = ", ".join("?" * len(ids))
    with closing(get_conn()) as conn:
        with conn:
            cur = conn.execute(f"DELETE FROM jobs WHERE id IN ({marks})", ids)
            return cur.rowcount


def change_status_tx(jid: str, to_status: str, from_status: str, note, event_time: str,
                     applied_at, ended_at, updated_at: str,
                     next_time=None, fail_stage=None, last_note=None, last_note_at=None) -> str:
    """事务内更新 job（含流转辅助列）+ 写一条状态流转事件，返回事件 id。"""
    eid = util.new_id()
    with closing(get_conn()) as conn:
        with conn:
            conn.execute(
                "UPDATE jobs SET status=?, applied_at=?, ended_at=?, updated_at=?,"
                " next_time=?, fail_stage=?, last_note=?, last_note_at=? WHERE id=?",
                (to_status, applied_at, ended_at, updated_at,
                 next_time, fail_stage, last_note, last_note_at, jid),
            )
            conn.execute(
                "INSERT INTO job_events (id, job_id, time, type, from_status, to_status, note, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (eid, jid, event_time, "状态流转", from_status, to_status, note, util.now_iso()),
            )
    return eid


def list_jobs_by_company(company_id: str) -> list:
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE company_id = ?", (company_id,)).fetchall()
    return [_job_from_row(r) for r in rows]


def set_company_null(company_id: str) -> None:
    with closing(get_conn()) as conn:
        with conn:
            conn.execute(
                "UPDATE jobs SET company_id=NULL, updated_at=? WHERE company_id=?",
                (util.now_iso(), company_id),
            )


def unlink_companies(ids: list) -> None:
    """批量删除公司前解绑岗位（删除公司不删岗位，仅置空 company_id 并刷新 updated_at）。"""
    if not ids:
        return
    marks = ", ".join("?" * len(ids))
    with closing(get_conn()) as conn:
        with conn:
            conn.execute(
                f"UPDATE jobs SET company_id=NULL, updated_at=? WHERE company_id IN ({marks})",
                [util.now_iso(), *ids],
            )


def count_by_resume(resume_id: str) -> int:
    with closing(get_conn()) as conn:
        return conn.execute("SELECT COUNT(*) FROM jobs WHERE resume_id = ?", (resume_id,)).fetchone()[0]


def clear_resume_refs(resume_id: str) -> None:
    with closing(get_conn()) as conn:
        with conn:
            conn.execute(
                "UPDATE jobs SET resume_id=NULL, resume_name=NULL, updated_at=? WHERE resume_id=?",
                (util.now_iso(), resume_id),
            )


def last_transition_time(jid: str):
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT MAX(time) FROM job_events WHERE job_id=? AND type='状态流转'", (jid,)
        ).fetchone()
    return row[0]


# ---------------- job_events ----------------
def get_event(eid: str):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM job_events WHERE id = ?", (eid,)).fetchone()
    return dict(row) if row else None


def list_events(job_id: str) -> list:
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT * FROM job_events WHERE job_id = ? ORDER BY time ASC, created_at ASC", (job_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------- companies ----------------
def get_company(cid):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (cid,)).fetchone()
    return dict(row) if row else None


def get_company_by_name(name: str):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM companies WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def list_companies(filters: dict | None = None) -> list:
    filters = filters or {}
    conds, params = [], []
    if filters.get("city"):
        conds.append("city LIKE ?")
        params.append(f"%{filters['city']}%")
    for col in ("industry", "nature"):
        if filters.get(col):
            conds.append(f"{col} = ?")
            params.append(filters[col])
    if filters.get("keyword"):
        kw = f"%{filters['keyword']}%"
        conds.append("name LIKE ?")
        params.append(kw)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with closing(get_conn()) as conn:
        rows = conn.execute(
            f"SELECT * FROM companies {where} ORDER BY created_at DESC, id", params
        ).fetchall()
    return [dict(r) for r in rows]


def create_company(data: dict) -> dict:
    now = util.now_iso()
    cid = data.get("id") or util.new_id()
    row = {
        "id": cid, "name": data.get("name"), "website": data.get("website"),
        "career_url": data.get("career_url"), "industry": data.get("industry"),
        "city": data.get("city"), "nature": data.get("nature"),
        "probe_status": data.get("probe_status") or "未探测", "ats_type": data.get("ats_type"),
        "notes": data.get("notes"), "last_fetched_at": data.get("last_fetched_at"),
        "last_fetch_result": data.get("last_fetch_result"),
        "created_at": data.get("created_at") or now,
    }
    cols = ", ".join(COMPANY_COLS)
    marks = ", ".join("?" * len(COMPANY_COLS))
    with closing(get_conn()) as conn:
        with conn:
            conn.execute(f"INSERT INTO companies ({cols}) VALUES ({marks})", [row[c] for c in COMPANY_COLS])
    return get_company(cid)


def update_company(cid: str, fields: dict) -> dict:
    sets, params = [], []
    for key, val in fields.items():
        if key not in COMPANY_COLS or key == "id":
            continue
        sets.append(f"{key} = ?")
        params.append(val)
    if sets:
        params.append(cid)
        with closing(get_conn()) as conn:
            with conn:
                conn.execute(f"UPDATE companies SET {', '.join(sets)} WHERE id = ?", params)
    return get_company(cid)


def delete_company(cid: str) -> None:
    with closing(get_conn()) as conn:
        with conn:
            conn.execute("DELETE FROM companies WHERE id = ?", (cid,))


def batch_delete_companies(ids: list) -> int:
    if not ids:
        return 0
    marks = ", ".join("?" * len(ids))
    with closing(get_conn()) as conn:
        with conn:
            cur = conn.execute(f"DELETE FROM companies WHERE id IN ({marks})", ids)
            return cur.rowcount


# ---------------- resumes ----------------
def get_resume(rid):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM resumes WHERE id = ?", (rid,)).fetchone()
    return _resume_from_row(row) if row else None


def list_resumes():
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM resumes ORDER BY updated_at DESC, id").fetchall()
    return [_resume_from_row(r) for r in rows]


def create_resume(data: dict) -> dict:
    now = util.now_iso()
    rid = data.get("id") or util.new_id()
    row = {
        "id": rid, "name": data.get("name"),
        "basic": _dump(data.get("basic") or {}),
        "education": _dump(data.get("education") or []),
        "experience": _dump(data.get("experience") or []),
        "projects": _dump(data.get("projects") or []),
        "skills": _dump(data.get("skills") or []),
        "summary": data.get("summary"),
        "pdf_file": data.get("pdf_file"),
        "created_at": data.get("created_at") or now,
        "updated_at": data.get("updated_at") or now,
    }
    cols = ", ".join(RESUME_COLS)
    marks = ", ".join("?" * len(RESUME_COLS))
    with closing(get_conn()) as conn:
        with conn:
            conn.execute(f"INSERT INTO resumes ({cols}) VALUES ({marks})", [row[c] for c in RESUME_COLS])
    return get_resume(rid)


def update_resume(rid: str, fields: dict) -> dict:
    sets, params = [], []
    fields = dict(fields)
    fields.setdefault("updated_at", util.now_iso())
    for key, val in fields.items():
        if key not in RESUME_COLS or key == "id":
            continue
        sets.append(f"{key} = ?")
        params.append(_dump(val))
    if sets:
        params.append(rid)
        with closing(get_conn()) as conn:
            with conn:
                conn.execute(f"UPDATE resumes SET {', '.join(sets)} WHERE id = ?", params)
    return get_resume(rid)


def delete_resume(rid: str) -> None:
    with closing(get_conn()) as conn:
        with conn:
            conn.execute("DELETE FROM resumes WHERE id = ?", (rid,))


# ---------------- 备份（事务内整表替换） ----------------
def replace_all(companies: list[dict], resumes: list[dict], jobs: list[dict]) -> None:
    """overwrite 模式：一个事务内清空并重插（jobs 级联清空 job_events）。"""
    with closing(get_conn()) as conn:
        with conn:
            conn.execute("DELETE FROM jobs")
            conn.execute("DELETE FROM companies")
            conn.execute("DELETE FROM resumes")
            for c in companies:
                row = {col: c.get(col) for col in COMPANY_COLS}
                row["created_at"] = row["created_at"] or util.now_iso()
                row["probe_status"] = row["probe_status"] or "未探测"
                conn.execute(
                    f"INSERT INTO companies ({', '.join(COMPANY_COLS)}) VALUES ({', '.join('?' * len(COMPANY_COLS))})",
                    [row[col] for col in COMPANY_COLS],
                )
            for r in resumes:
                row = {col: r.get(col) for col in RESUME_COLS}
                row["basic"] = _dump(row["basic"] or {})
                for col in ("education", "experience", "projects", "skills"):
                    row[col] = _dump(row[col] or [])
                if not row["created_at"] or not row["updated_at"]:
                    row["created_at"] = row["created_at"] or util.now_iso()
                    row["updated_at"] = row["updated_at"] or util.now_iso()
                conn.execute(
                    f"INSERT INTO resumes ({', '.join(RESUME_COLS)}) VALUES ({', '.join('?' * len(RESUME_COLS))})",
                    [row[col] for col in RESUME_COLS],
                )
            for j in jobs:
                row = {col: j.get(col) for col in JOB_COLS}
                row["status"] = row["status"] or "待投递"
                row["notes"] = _dump(row["notes"] or [])
                if not row["created_at"] or not row["updated_at"]:
                    row["created_at"] = row["created_at"] or util.now_iso()
                    row["updated_at"] = row["updated_at"] or util.now_iso()
                conn.execute(
                    f"INSERT INTO jobs ({', '.join(JOB_COLS)}) VALUES ({', '.join('?' * len(JOB_COLS))})",
                    [row[col] for col in JOB_COLS],
                )
