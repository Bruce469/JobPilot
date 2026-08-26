"""业务层：组合 DAO 实现业务规则（状态流转 / 导入去重 / 备份 / 统计）。"""
import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import config, dao, db, util
from .errors import APIError, conflict, import_error, not_found, validation_error
from .fetcher import normalize
from .fetcher import resolve as resolve_mod
from .fetcher import tasks as fetcher_tasks


def _last_export_file() -> Path:
    """上次成功导出时间戳文件（X-3 启动备份提醒），按当前 DB 路径定位。"""
    return Path(config.DB_PATH).parent / "last_export.json"


# ---------------- 岗位 jobs ----------------
def get_job(job_id: str) -> dict:
    job = dao.get_job(job_id)
    if not job:
        raise not_found("岗位", job_id)
    job["events"] = dao.list_events(job_id)
    return job


def list_jobs(filters: dict) -> dict:
    items, total = dao.list_jobs(filters)
    return {"items": items, "total": total}


def _validate_refs(payload: dict) -> None:
    cid = payload.get("company_id")
    if cid and not dao.get_company(cid):
        raise not_found("关联公司", cid)
    rid = payload.get("resume_id")
    if rid and not dao.get_resume(rid):
        raise not_found("关联简历", rid)


def create_job(payload: dict) -> dict:
    if not payload.get("company") or not str(payload.get("company", "")).strip():
        raise validation_error("公司名必填")
    _validate_refs(payload)
    data = dict(payload)
    if data.get("resume_id"):
        data["resume_name"] = dao.get_resume(data["resume_id"])["name"]
    return dao.create_job(data)


def update_job(job_id: str, fields: dict) -> dict:
    if not dao.get_job(job_id):
        raise not_found("岗位", job_id)
    data = dict(fields)
    if data.get("company") is not None and not str(data["company"]).strip():
        raise validation_error("公司名不能为空")
    _validate_refs(data)
    if "resume_id" in data:
        if data.get("resume_id"):
            data["resume_name"] = dao.get_resume(data["resume_id"])["name"]
        else:
            data["resume_name"] = None
    # status/ended_at 不经此接口变更，走状态流转接口
    data.pop("status", None)
    data.pop("ended_at", None)
    return dao.update_job(job_id, data)


def delete_job(job_id: str) -> None:
    if not dao.get_job(job_id):
        raise not_found("岗位", job_id)
    dao.delete_job(job_id)  # 级联删 job_events


def batch_delete(ids: list) -> int:
    return dao.batch_delete(ids)


def change_status(job_id: str, to_status: str, note=None, time=None) -> tuple[dict, dict | None]:
    job = dao.get_job(job_id)
    if not job:
        raise not_found("岗位", job_id)
    if to_status not in dao.STATUS_ALL:
        raise validation_error(f"非法状态：{to_status}")
    event_time = time or util.now_iso()
    if not util.parse_dt(event_time):
        raise validation_error("time 格式非法（应为 YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS）")
    if job["status"] == to_status:
        return job, None  # 同状态不产生事件

    updated_at = util.now_iso()
    applied_at = job.get("applied_at")
    ended_at = job.get("ended_at")
    if to_status == "已投递" and not applied_at:
        applied_at = util.date_of(event_time)
    if to_status in dao.TERMINAL:
        ended_at = util.date_of(event_time)  # 进终态记 ended_at
    elif ended_at:
        ended_at = None  # 从终态回退清 ended_at
    eid = dao.change_status_tx(job_id, to_status, job["status"], note, event_time,
                               applied_at, ended_at, updated_at)
    return dao.get_job(job_id), dao.get_event(eid)


def import_jobs(company_id: str, items: list[dict]) -> dict:
    company = dao.get_company(company_id)
    if not company:
        raise not_found("公司", company_id)
    existing = dao.list_jobs_by_company(company_id)
    src_ids = {j["source_job_id"] for j in existing if j.get("source_job_id")}
    pos_city = {(normalize.normalize_position(j.get("position")), j.get("city")) for j in existing}

    added = skipped = failed = 0
    added_ids, failures = [], []
    for i, item in enumerate(items):
        position = str(item.get("position") or "").strip()
        if not position:
            failed += 1
            failures.append({"index": i, "reason": "缺少岗位名 position"})
            continue
        try:
            src_id = item.get("source_job_id")
            if src_id and src_id in src_ids:
                skipped += 1
                continue
            norm = normalize.normalize_position(position)
            if not src_id and (norm, item.get("city")) in pos_city:
                skipped += 1
                continue
            job = dao.create_job({
                "company": company["name"],
                "company_id": company_id,
                "position": position,
                "job_type": item.get("job_type"),
                "degree": item.get("degree"),
                "city": item.get("city"),
                "industry": item.get("industry") or company.get("industry"),  # 导入岗位自动带入公司行业
                "channel": item.get("channel") or "官网",
                "job_url": item.get("job_url"),
                "source_job_id": src_id,
                "publish_date": item.get("publish_date"),
                "deadline": item.get("deadline"),
            })
            if src_id:
                src_ids.add(src_id)
            pos_city.add((norm, item.get("city")))
            added += 1
            added_ids.append(job["id"])
        except Exception as exc:  # 单条失败不影响其余
            failed += 1
            failures.append({"index": i, "reason": str(exc)})
    dao.update_company(company_id, {
        "last_fetched_at": util.now_iso(),
        "last_fetch_result": f"新增 {added} 条，跳过 {skipped} 条，失败 {failed} 条",
    })
    return {"added": added, "skipped": skipped, "failed": failed,
            "added_ids": added_ids, "failures": failures}


# ---------------- 简历 resumes ----------------
def get_resume(resume_id: str) -> dict:
    resume = dao.get_resume(resume_id)
    if not resume:
        raise not_found("简历", resume_id)
    return resume


def list_resumes() -> dict:
    items = dao.list_resumes()
    return {"items": items, "total": len(items)}


def create_resume(data: dict) -> dict:
    return dao.create_resume(data)


def update_resume(resume_id: str, fields: dict) -> dict:
    if not dao.get_resume(resume_id):
        raise not_found("简历", resume_id)
    return dao.update_resume(resume_id, fields)


def delete_resume(resume_id: str, force: bool):
    """被岗位引用时先返回引用数（供前端二次确认）；force=true 才真正删除并置空引用。"""
    if not dao.get_resume(resume_id):
        raise not_found("简历", resume_id)
    refs = dao.count_by_resume(resume_id)
    if refs > 0 and not force:
        return {"referenced_by": refs, "deleted": False}
    if refs > 0:
        dao.clear_resume_refs(resume_id)
    dao.delete_resume(resume_id)
    return None


# ---------------- 公司 companies ----------------
def get_company(company_id: str) -> dict:
    company = dao.get_company(company_id)
    if not company:
        raise not_found("公司", company_id)
    return company


def list_companies(filters: dict | None = None) -> dict:
    filters = filters or {}
    items = dao.list_companies(filters)
    return {"items": items, "total": len(items)}


def create_company(payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    website = str(payload.get("website") or "").strip()
    if not name or not website:
        raise validation_error("公司名与官网地址必填")
    if dao.get_company_by_name(name):
        raise conflict("公司名已存在", {"name": name})
    return dao.create_company({"name": name, "website": website,
                               "industry": payload.get("industry"),
                               "city": payload.get("city"),
                               "nature": payload.get("nature"),
                               "notes": payload.get("notes")})


def update_company(company_id: str, fields: dict) -> dict:
    company = dao.get_company(company_id)
    if not company:
        raise not_found("公司", company_id)
    new_name = str(fields.get("name") or "").strip()
    if new_name:
        existing = dao.get_company_by_name(new_name)
        if existing and existing["id"] != company_id:
            raise conflict("公司名已存在", {"name": new_name})
        fields = dict(fields)
        fields["name"] = new_name
    if "name" in fields and not fields.get("name"):
        raise validation_error("公司名不能为空")
    return dao.update_company(company_id, fields)


def delete_company(company_id: str) -> None:
    company = dao.get_company(company_id)
    if not company:
        raise not_found("公司", company_id)
    dao.set_company_null(company_id)  # 删除公司不删岗位，仅置空 company_id
    dao.delete_company(company_id)


def batch_delete_companies(ids: list) -> int:
    """批量删除公司：先解绑岗位（保留岗位、置空 company_id），再物理删除。"""
    dao.unlink_companies(ids)
    return dao.batch_delete_companies(ids)


def submit_batch_probe(ids: list) -> str:
    """提交批量探测任务（POST /api/companies/batch-probe），返回 job_id。"""
    if not ids:
        raise validation_error("请先勾选要探测的公司")
    return fetcher_tasks.submit("probe_batch", {"company_ids": list(ids)})


def submit_batch_resolve(ids: list) -> str:
    """提交批量补全任务（POST /api/companies/batch-resolve），返回 job_id。

    补全结果自动写入缺失字段（仅填充 website/industry/career_url 为空的字段，不覆盖已有值）。
    """
    if not ids:
        raise validation_error("请先勾选要补全的公司")
    return fetcher_tasks.submit("resolve", {"company_ids": list(ids)})


def import_companies(names: list, resolve: bool = False) -> dict:
    """公司批量导入（PRD 4.12）：按行去空、批内归一化去重、跳过已存在（归一化匹配）。

    resolve=False 同步返回 {added, skipped, skipped_names, added_ids}；
    resolve=True 在创建后提交异步批量补全任务，附加返回 job_id（补全结果不落库）。
    """
    clean = [str(n or "").strip() for n in names]
    clean = [n for n in clean if n]
    if not clean:
        raise validation_error("公司名单不能为空")
    existing = dao.list_companies()
    existing_norm = {normalize.normalize_company(c["name"]): c for c in existing}
    added = skipped = 0
    added_ids, skipped_names = [], []
    seen = set()
    for name in clean:
        norm = normalize.normalize_company(name)
        if norm in seen:  # 批内归一化重名（含首尾空格差异）
            skipped += 1
            skipped_names.append(name)
            continue
        seen.add(norm)
        if norm in existing_norm:  # 与已有公司归一化重名
            skipped += 1
            skipped_names.append(name)
            continue
        company = dao.create_company({"name": name, "website": "", "probe_status": "未探测"})
        added += 1
        added_ids.append(company["id"])
    result = {"added": added, "skipped": skipped, "skipped_names": skipped_names, "added_ids": added_ids}
    if resolve and added_ids:
        result["job_id"] = fetcher_tasks.submit("resolve", {"company_ids": added_ids})
    return result


RESOLVE_SYNC_TIMEOUT = 40.0  # 同步补全整体预算（搜索兜底可能较慢，到点放弃并返回已获结果）


def resolve_company_by_name(name: str) -> dict:
    """POST /api/companies/resolve：仅凭公司名自动补全（不落库）。"""
    name = str(name or "").strip()
    if not name:
        raise validation_error("公司名不能为空")
    return resolve_mod.resolve_company(name, time.monotonic() + RESOLVE_SYNC_TIMEOUT)


def resolve_company_for_id(company_id: str) -> dict:
    """POST /api/companies/{id}/resolve：对已有公司自动补全（不落库）。"""
    company = dao.get_company(company_id)
    if not company:
        raise not_found("公司", company_id)
    result = resolve_mod.resolve_company(company["name"], time.monotonic() + RESOLVE_SYNC_TIMEOUT)
    result["company_id"] = company_id
    return result


# ---------------- 备份 ----------------
def export_backup() -> dict:
    data = {
        "schema_version": db.current_schema_version(),
        "exported_at": util.now_iso(),
        "jobs": dao.all_jobs(),
        "companies": dao.list_companies(),
        "resumes": dao.list_resumes(),
    }
    _write_last_export(data["exported_at"])
    return data


def _write_last_export(ts: str) -> None:
    try:
        file = _last_export_file()
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps({"exported_at": ts}), encoding="utf-8")
    except OSError:
        pass


def last_export_info() -> dict:
    """启动备份提醒：距上次成功导出 >7 天提示。"""
    last = None
    file = _last_export_file()
    if file.exists():
        try:
            last = json.loads(file.read_text(encoding="utf-8")).get("exported_at")
        except (json.JSONDecodeError, OSError):
            pass
    days = None
    if last:
        try:
            days = (datetime.now() - datetime.fromisoformat(last)).days
        except ValueError:
            days = None
    return {"last_exported_at": last, "days_since": days, "need_backup": (days or 0) > 7}


def import_backup(payload: dict) -> dict:
    mode = payload.get("mode")
    if mode not in ("merge", "overwrite"):
        raise import_error("mode 必须为 merge 或 overwrite")
    sv = payload.get("schema_version")
    cur = db.current_schema_version()
    if not isinstance(sv, int) or sv <= 0 or sv > cur:
        raise import_error(f"备份 schema_version 非法或过高（当前支持 {cur}）", {"schema_version": sv})
    jobs, companies, resumes = payload.get("jobs") or [], payload.get("companies") or [], payload.get("resumes") or []
    # 预校验必填字段，非法则 422 且不改动现有数据
    for c in companies:
        if not (c.get("id") and c.get("name") and c.get("website")):
            raise import_error("公司数据缺少必填字段（id/name/website）")
    for r in resumes:
        if not (r.get("id") and r.get("name") and isinstance(r.get("basic"), dict) and r["basic"].get("name")):
            raise import_error("简历数据缺少必填字段（id/name/basic.name）")
    for j in jobs:
        if not (j.get("id") and j.get("company")):
            raise import_error("岗位数据缺少必填字段（id/company）")

    result = {"mode": mode, "jobs_added": 0, "jobs_skipped": 0,
              "companies_added": 0, "resumes_added": 0, "errors": []}
    if mode == "overwrite":
        # 引用兜底：备份内不存在的公司/简历置空，避免外键约束失败
        company_ids = {c["id"] for c in companies}
        resume_ids = {r["id"] for r in resumes}
        cleaned_jobs = []
        for j in jobs:
            j = dict(j)
            if j.get("company_id") and j["company_id"] not in company_ids:
                j["company_id"] = None
            if j.get("resume_id") and j["resume_id"] not in resume_ids:
                j["resume_id"] = None
                j["resume_name"] = None
            elif j.get("resume_id") and not j.get("resume_name"):
                r = next((x for x in resumes if x["id"] == j["resume_id"]), None)
                if r:
                    j["resume_name"] = r.get("name")
            cleaned_jobs.append(j)
        dao.replace_all(companies, resumes, cleaned_jobs)
        result.update(jobs_added=len(cleaned_jobs), companies_added=len(companies), resumes_added=len(resumes))
        return result

    # merge：同 id 以本机为准跳过；岗位引用按 id 恢复，缺引用对象置空
    for c in companies:
        if not dao.get_company(c["id"]):
            try:
                dao.create_company(c)
                result["companies_added"] += 1
            except sqlite3.IntegrityError:
                result["errors"].append({"type": "company", "id": c["id"], "reason": "公司名冲突，以本机为准"})
    for r in resumes:
        if not dao.get_resume(r["id"]):
            dao.create_resume(r)
            result["resumes_added"] += 1
    for j in jobs:
        if dao.get_job(j["id"]):
            result["jobs_skipped"] += 1
            continue
        j = dict(j)
        cid = j.get("company_id")
        if cid and not dao.get_company(cid):
            j["company_id"] = None
        rid = j.get("resume_id")
        if rid and not dao.get_resume(rid):
            j["resume_id"] = None
            j["resume_name"] = None
        elif rid:
            j["resume_name"] = dao.get_resume(rid)["name"]
        dao.create_job(j)
        result["jobs_added"] += 1
    return result


# ---------------- 统计（PRD 4.8 口径，M2 出界面，M1 契约就绪） ----------------
def compute_stats() -> dict:
    jobs = dao.all_jobs()
    now = datetime.now()
    active_set = {"已投递", "简历筛选", "笔试", "一面", "二面", "三面/HR面"}

    total_applied = sum(1 for j in jobs if j["status"] != "待投递")
    active = sum(1 for j in jobs if j["status"] in active_set)
    offered = sum(1 for j in jobs if j["status"] == "已Offer")
    rejected = sum(1 for j in jobs if j["status"] in ("已拒绝", "已放弃"))

    # 待跟进：进行中且距上次状态流转 > 3 天（无事件时以 applied_at 计）
    pending_followup = 0
    for j in jobs:
        if j["status"] not in active_set:
            continue
        last = dao.last_transition_time(j["id"]) or j.get("applied_at")
        t = util.parse_dt(last)
        if t and (now - t).total_seconds() > 3 * 86400:
            pending_followup += 1

    # 漏斗：从「已投递」起、不含「待投递」
    counts: dict[str, int] = {}
    for j in jobs:
        counts[j["status"]] = counts.get(j["status"], 0) + 1
    funnel_order = ["已投递", "简历筛选", "笔试", "一面", "二面", "三面/HR面", "已Offer", "已拒绝", "已放弃"]
    funnel = [{"status": s, "count": counts[s]} for s in funnel_order if counts.get(s)]

    channel: dict[str, int] = {}
    for j in jobs:
        key = j.get("channel") or "未填写"
        channel[key] = channel.get(key, 0) + 1
    channel_dist = [{"channel": k, "count": v} for k, v in sorted(channel.items(), key=lambda x: -x[1])]

    return {
        "total_applied": total_applied,
        "active": active,
        "offered": offered,
        "rejected": rejected,
        "pending_followup": pending_followup,
        "funnel": funnel,
        "channel_dist": channel_dist,
        "weekly_trend": _weekly_trend(jobs, now),
    }


def _weekly_trend(jobs: list[dict], now: datetime) -> list[dict]:
    """近 4 周（含本周）按 applied_at 统计，week_start 为周一。"""
    current = now - timedelta(days=now.weekday())
    weeks = [current - timedelta(days=7 * i) for i in range(4)]
    out = []
    for start in reversed(weeks):  # 时间升序
        end = start + timedelta(days=7)
        count = 0
        for j in jobs:
            t = util.parse_dt(j.get("applied_at"))
            if t and start.date() <= t.date() < end.date():
                count += 1
        out.append({"week_start": start.date().isoformat(), "count": count})
    return out
