"""Pydantic 请求模型（架构 4.2 契约）。"""
from typing import Optional

from pydantic import BaseModel, Field


# ---------------- 岗位 jobs ----------------
class JobCandidate(BaseModel):
    """岗位候选（岗位导入条目），字段即 jobs 表抓取字段。"""
    position: str
    city: Optional[str] = None
    job_url: Optional[str] = None
    source_job_id: Optional[str] = None
    deadline: Optional[str] = None
    degree: Optional[str] = None
    job_type: Optional[str] = None  # 校招/社招/实习


class JobCreate(BaseModel):
    company: str
    company_id: Optional[str] = None
    position: Optional[str] = None
    job_type: Optional[str] = None
    degree: Optional[str] = None
    city: Optional[str] = None
    industry: Optional[str] = None
    channel: Optional[str] = None
    job_url: Optional[str] = None
    source_job_id: Optional[str] = None
    publish_date: Optional[str] = None
    deadline: Optional[str] = None
    applied_at: Optional[str] = None
    resume_id: Optional[str] = None
    notes: Optional[list] = None


class JobUpdate(BaseModel):
    company: Optional[str] = None
    company_id: Optional[str] = None
    position: Optional[str] = None
    job_type: Optional[str] = None
    degree: Optional[str] = None
    city: Optional[str] = None
    industry: Optional[str] = None
    channel: Optional[str] = None
    job_url: Optional[str] = None
    source_job_id: Optional[str] = None
    publish_date: Optional[str] = None
    deadline: Optional[str] = None
    applied_at: Optional[str] = None
    next_time: Optional[str] = None
    fail_stage: Optional[str] = None
    resume_id: Optional[str] = None
    notes: Optional[list] = None


class JobStatusIn(BaseModel):
    status: str
    note: Optional[str] = None
    time: Optional[str] = None  # 可选，默认服务端当前时间
    next_time: Optional[str] = None  # 等待环节计划时间（仅等待态生效，离开自动清空）
    fail_stage: Optional[str] = None  # 被拒环节标签（仅已拒绝生效，重新推进自动清空）


class BatchDelete(BaseModel):
    ids: list[str]


class JobImportIn(BaseModel):
    company_id: str
    jobs: list[JobCandidate] = Field(default_factory=list)


# ---------------- 简历 resumes ----------------
class ResumeBasic(BaseModel):
    name: str
    phone: str = ""
    email: str = ""
    target_position: str = ""
    city: str = ""


class EducationItem(BaseModel):
    school: str = ""
    major: Optional[str] = None
    degree: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class ExperienceItem(BaseModel):
    company: str = ""
    position: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    responsibilities: Optional[str] = None


class ProjectItem(BaseModel):
    name: str = ""
    role: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class ResumeIn(BaseModel):
    name: str
    basic: ResumeBasic
    education: list[EducationItem] = []
    experience: list[ExperienceItem] = []
    projects: list[ProjectItem] = []
    skills: list[str] = []
    summary: Optional[str] = None


class ResumeUpdate(BaseModel):
    name: Optional[str] = None
    basic: Optional[ResumeBasic] = None
    education: Optional[list[EducationItem]] = None
    experience: Optional[list[ExperienceItem]] = None
    projects: Optional[list[ProjectItem]] = None
    skills: Optional[list[str]] = None
    summary: Optional[str] = None


# ---------------- 公司 companies ----------------
class CompanyIn(BaseModel):
    name: str
    website: str
    industry: Optional[str] = None
    city: Optional[str] = None
    nature: Optional[str] = None
    notes: Optional[str] = None


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    career_url: Optional[str] = None
    industry: Optional[str] = None
    city: Optional[str] = None
    nature: Optional[str] = None
    notes: Optional[str] = None
    processed: Optional[bool] = None  # 已处理/未处理标签（True=已处理）


class CompanyImportItem(BaseModel):
    name: str
    city: Optional[str] = None
    industry: Optional[str] = None
    nature: Optional[str] = None
    website: Optional[str] = None


class CompanyImportIn(BaseModel):
    companies: list[CompanyImportItem] = Field(default_factory=list)  # txt 按行拆出的公司信息（名称+可选属性）
    names: list[str] = Field(default_factory=list)  # 兼容旧版：仅公司名列表
    resolve: bool = False                            # 是否创建后异步批量自动补全


class CompanyResolveIn(BaseModel):
    name: str  # 仅凭公司名自动补全（不落库）


class CompanyBatchIn(BaseModel):
    ids: list[str]  # 批量探测/批量补全的公司 id 列表


# ---------------- 备份 backup ----------------
class BackupCompanyItem(BaseModel):
    id: str
    name: str
    website: str
    career_url: Optional[str] = None
    industry: Optional[str] = None
    city: Optional[str] = None
    nature: Optional[str] = None
    probe_status: Optional[str] = None
    ats_type: Optional[str] = None
    notes: Optional[str] = None
    last_fetched_at: Optional[str] = None
    last_fetch_result: Optional[str] = None
    processed: Optional[int] = None  # 0=未处理 1=已处理；旧备份缺失时导入默认未处理
    created_at: Optional[str] = None


class BackupResumeItem(BaseModel):
    id: str
    name: str
    basic: dict
    education: Optional[list] = None
    experience: Optional[list] = None
    projects: Optional[list] = None
    skills: Optional[list] = None
    summary: Optional[str] = None
    pdf_file: Optional[str] = None  # 源 PDF 文件名（本体不在 JSON 备份内）
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BackupJobItem(BaseModel):
    id: str
    company: str
    company_id: Optional[str] = None
    position: Optional[str] = None
    job_type: Optional[str] = None
    degree: Optional[str] = None
    city: Optional[str] = None
    industry: Optional[str] = None
    channel: Optional[str] = None
    job_url: Optional[str] = None
    source_job_id: Optional[str] = None
    publish_date: Optional[str] = None
    deadline: Optional[str] = None
    applied_at: Optional[str] = None
    status: Optional[str] = None
    ended_at: Optional[str] = None
    next_time: Optional[str] = None
    fail_stage: Optional[str] = None
    last_note: Optional[str] = None
    last_note_at: Optional[str] = None
    resume_id: Optional[str] = None
    resume_name: Optional[str] = None
    notes: Optional[list] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BackupImportIn(BaseModel):
    schema_version: int
    mode: str  # merge | overwrite
    jobs: list[BackupJobItem] = []
    companies: list[BackupCompanyItem] = []
    resumes: list[BackupResumeItem] = []
