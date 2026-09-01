"""API 路由层（架构 4.2 端点清单，前缀 /api）。"""
from typing import Optional

from fastapi import APIRouter, File, Query, Response, UploadFile
from fastapi.responses import FileResponse

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
    job, event = services.change_status(job_id, body.status, body.note, body.time,
                                        body.next_time, body.fail_stage)
    return {"job": job, "event": event}


# ---------------- 简历 resumes ----------------
@router.get("/resumes")
def list_resumes():
    return services.list_resumes()


@router.post("/resumes", status_code=201)
def create_resume(body: schemas.ResumeIn):
    return services.create_resume(body.model_dump())


@router.post("/resumes/upload-pdf", status_code=201)
async def upload_resume_pdf(file: UploadFile = File(...)):
    """上传简历源 PDF（multipart 字段名 file），返回带 pdf_file 的简历对象。

    先按服务层上限截读，避免超大文件整体占内存；大小/类型校验在服务层统一处理。
    """
    max_size = services.MAX_RESUME_PDF_SIZE
    content = await file.read(max_size + 1)  # 只多读 1 字节即可判定超限
    return services.create_resume_with_pdf(file.filename or "", content)


@router.get("/resumes/{resume_id}")
def get_resume(resume_id: str):
    return services.get_resume(resume_id)


@router.get("/resumes/{resume_id}/pdf")
def get_resume_pdf(resume_id: str):
    """在线预览简历源 PDF（inline，ASCII 文件名回退避免中文头报错）。"""
    path = services.get_resume_pdf_path(resume_id)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{resume_id}.pdf",  # 下载名用 id 而非原始中文名，规避 Content-Disposition 编码问题
        content_disposition_type="inline",
    )


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
def list_companies(
    city: Optional[str] = None,
    industry: Optional[str] = None,
    nature: Optional[str] = None,
    processed: Optional[int] = None,
    keyword: Optional[str] = None,
):
    # city/industry 逗号分隔多值（与 list_jobs 的 status 一致），split 后去空格去空项
    city_list = [c.strip() for c in city.split(",") if c.strip()] if city else None
    industry_list = [i.strip() for i in industry.split(",") if i.strip()] if industry else None
    return services.list_companies({
        "city": city_list, "industry": industry_list, "nature": nature,
        "processed": processed, "keyword": keyword,
    })


@router.get("/companies/facets")
def list_company_facets():
    """公司库筛选候选池：{cities, industries, natures} 各为 DISTINCT 非空值排序列表。"""
    return services.company_facets()


@router.post("/companies", status_code=201)
def create_company(body: schemas.CompanyIn):
    return services.create_company(body.model_dump())


@router.post("/companies/import")
def import_companies(body: schemas.CompanyImportIn):
    # 优先结构化条目（名称+城市/行业/性质/官网），为空时兼容旧版纯公司名列表
    items = [c.model_dump() for c in body.companies] or list(body.names)
    return services.import_companies(items, body.resolve)


@router.post("/companies/resolve")
def resolve_company(body: schemas.CompanyResolveIn):
    return services.resolve_company_by_name(body.name)


@router.post("/companies/batch-delete")
def batch_delete_companies(body: schemas.BatchDelete):
    return {"deleted": services.batch_delete_companies(body.ids)}


@router.post("/companies/batch-resolve", status_code=202)
def batch_resolve_companies(body: schemas.CompanyBatchIn):
    job_id = services.submit_batch_resolve(body.ids)
    return {"job_id": job_id, "type": "resolve"}


@router.post("/companies/{company_id}/resolve")
def resolve_existing_company(company_id: str):
    return services.resolve_company_for_id(company_id)


@router.get("/companies/{company_id}/jobs")
def list_company_jobs(company_id: str):
    """该公司全部岗位（公司库展开列表数据源）。"""
    return services.list_company_jobs(company_id)


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
