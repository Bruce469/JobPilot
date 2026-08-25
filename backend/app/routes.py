"""API 路由层（架构 4.2 端点清单，前缀 /api）。"""
from typing import Optional

from fastapi import APIRouter, Query, Response

from . import config, db, schemas, services
from .errors import APIError
from .fetcher import tasks as fetcher_tasks

router = APIRouter()


# ---------------- 系统 ----------------
@router.get("/boot")
def boot():
    return {
        "token": config.TOKEN,
        "schema_version": db.current_schema_version(),
        "app": {"name": config.APP_NAME, "version": config.APP_VERSION},
        "backup": services.last_export_info(),   # 启动备份提醒（X-3）
    }


# ---------------- 岗位 jobs ----------------
@router.get("/jobs")
def list_jobs(
    status: Optional[str] = None,
    company: Optional[str] = None,
    city: Optional[str] = None,
    industry: Optional[str] = None,
    channel: Optional[str] = None,
    keyword: Optional[str] = None,
    include_ended: bool = False,
    sort: str = "updated_at",
    sort_dir: str = "desc",
):
    status_list = [s.strip() for s in status.split(",") if s.strip()] if status else None
    return services.list_jobs({
        "status": status_list, "company": company, "city": city,
        "industry": industry, "channel": channel, "keyword": keyword,
        "include_ended": include_ended, "sort": sort, "sort_dir": sort_dir,
    })


@router.post("/jobs", status_code=201)
def create_job(body: schemas.JobCreate):
    return services.create_job(body.model_dump())


@router.post("/jobs/batch-delete")
def batch_delete(body: schemas.BatchDelete):
    return {"deleted": services.batch_delete(body.ids)}


@router.post("/jobs/import")
def import_jobs(body: schemas.JobImportIn):
    return services.import_jobs(body.company_id, [j.model_dump() for j in body.jobs])


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    return services.get_job(job_id)


@router.put("/jobs/{job_id}")
def update_job(job_id: str, body: schemas.JobUpdate):
    return services.update_job(job_id, body.model_dump(exclude_unset=True))


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    services.delete_job(job_id)
    return Response(status_code=204)


@router.post("/jobs/{job_id}/status")
def change_status(job_id: str, body: schemas.JobStatusIn):
    job, event = services.change_status(job_id, body.status, body.note, body.time)
    return {"job": job, "event": event}


# ---------------- 简历 resumes ----------------
@router.get("/resumes")
def list_resumes():
    return services.list_resumes()


@router.post("/resumes", status_code=201)
def create_resume(body: schemas.ResumeIn):
    return services.create_resume(body.model_dump())


@router.get("/resumes/{resume_id}")
def get_resume(resume_id: str):
    return services.get_resume(resume_id)


@router.put("/resumes/{resume_id}")
def update_resume(resume_id: str, body: schemas.ResumeUpdate):
    return services.update_resume(resume_id, body.model_dump(exclude_unset=True))


@router.delete("/resumes/{resume_id}")
def delete_resume(resume_id: str, force: bool = False):
    result = services.delete_resume(resume_id, force)
    if result is None:
        return Response(status_code=204)
    return result


# ---------------- 公司 companies ----------------
@router.get("/companies")
def list_companies():
    return services.list_companies()


@router.post("/companies", status_code=201)
def create_company(body: schemas.CompanyIn):
    return services.create_company(body.model_dump())


@router.post("/companies/import")
def import_companies(body: schemas.CompanyImportIn):
    return services.import_companies(body.names, body.resolve)


@router.post("/companies/resolve")
def resolve_company(body: schemas.CompanyResolveIn):
    return services.resolve_company_by_name(body.name)


@router.post("/companies/batch-delete")
def batch_delete_companies(body: schemas.BatchDelete):
    return {"deleted": services.batch_delete_companies(body.ids)}


@router.post("/companies/batch-probe", status_code=202)
def batch_probe_companies(body: schemas.CompanyBatchIn):
    job_id = services.submit_batch_probe(body.ids)
    return {"job_id": job_id, "type": "probe_batch"}


@router.post("/companies/batch-resolve", status_code=202)
def batch_resolve_companies(body: schemas.CompanyBatchIn):
    job_id = services.submit_batch_resolve(body.ids)
    return {"job_id": job_id, "type": "resolve"}


@router.post("/companies/{company_id}/probe", status_code=202)
def probe_company(company_id: str):
    services.get_company(company_id)
    job_id = fetcher_tasks.submit("probe", {"company_id": company_id})
    return {"job_id": job_id, "type": "probe"}


@router.post("/companies/{company_id}/fetch", status_code=202)
def fetch_company_jobs(company_id: str, body: Optional[schemas.CompanyFetchIn] = None):
    services.get_company(company_id)
    career_url = body.career_url if body else None
    job_id = fetcher_tasks.submit("fetch", {"company_id": company_id, "career_url": career_url})
    return {"job_id": job_id, "type": "fetch"}


@router.post("/companies/{company_id}/resolve")
def resolve_existing_company(company_id: str):
    return services.resolve_company_for_id(company_id)


@router.get("/companies/{company_id}")
def get_company(company_id: str):
    return services.get_company(company_id)


@router.put("/companies/{company_id}")
def update_company(company_id: str, body: schemas.CompanyUpdate):
    return services.update_company(company_id, body.model_dump(exclude_unset=True))


@router.delete("/companies/{company_id}", status_code=204)
def delete_company(company_id: str):
    services.delete_company(company_id)
    return Response(status_code=204)


# ---------------- 任务 tasks ----------------
@router.get("/tasks/{job_id}")
def get_task(job_id: str):
    task = fetcher_tasks.get(job_id)
    if not task:
        raise APIError(404, "NOT_FOUND", "任务不存在", {"job_id": job_id})
    return task


# ---------------- 备份 backup ----------------
@router.get("/backup/export")
def export_backup():
    return services.export_backup()


@router.post("/backup/import")
def import_backup(body: schemas.BackupImportIn):
    return services.import_backup(body.model_dump())


# ---------------- 统计 stats ----------------
@router.get("/stats")
def stats():
    return services.compute_stats()
