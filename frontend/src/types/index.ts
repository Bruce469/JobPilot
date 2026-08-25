// 领域类型定义（对应 backend/app/schemas.py 与 DAO 行结构）
export interface JobEvent {
  id: string
  job_id: string
  time: string
  type: string
  from_status: string | null
  to_status: string | null
  note: string | null
  created_at: string
}

export interface Job {
  id: string
  company: string
  company_id: string | null
  position: string | null
  job_type: string | null
  degree: string | null
  city: string | null
  industry: string | null
  channel: string | null
  job_url: string | null
  source_job_id: string | null
  publish_date: string | null
  deadline: string | null
  applied_at: string | null
  status: string
  ended_at: string | null
  resume_id: string | null
  resume_name: string | null
  notes: { time: string; content: string }[]
  created_at: string
  updated_at: string
}

export interface JobDetail extends Job {
  events: JobEvent[]
}

export interface JobCandidate {
  position: string
  city?: string | null
  job_url?: string | null
  source_job_id?: string | null
  deadline?: string | null
  degree?: string | null
  job_type?: string | null
}

export interface ResumeBasic {
  name: string
  phone: string
  email: string
  target_position: string
  city: string
}

export interface EducationItem {
  school: string
  major?: string | null
  degree?: string | null
  start_date?: string | null
  end_date?: string | null
  description?: string | null
}

export interface ExperienceItem {
  company: string
  position?: string | null
  start_date?: string | null
  end_date?: string | null
  responsibilities?: string | null
}

export interface ProjectItem {
  name: string
  role?: string | null
  start_date?: string | null
  end_date?: string | null
  description?: string | null
}

export interface Resume {
  id: string
  name: string
  basic: ResumeBasic
  education: EducationItem[]
  experience: ExperienceItem[]
  projects: ProjectItem[]
  skills: string[]
  summary: string | null
  created_at: string
  updated_at: string
}

export interface ResumePayload {
  name: string
  basic: ResumeBasic
  education?: EducationItem[]
  experience?: ExperienceItem[]
  projects?: ProjectItem[]
  skills?: string[]
  summary?: string | null
}

export interface Company {
  id: string
  name: string
  website: string
  career_url: string | null
  industry: string | null
  probe_status: string | null
  ats_type: string | null
  notes: string | null
  last_fetched_at: string | null
  last_fetch_result: string | null
  created_at: string
}

export interface CompanyPayload {
  name: string
  website: string
  industry?: string | null
  notes?: string | null
}

/** 单公司按名称补全结果（POST /api/companies/resolve、POST /api/companies/{id}/resolve、批量 resolve 任务结果项） */
export interface CompanyResolveResult {
  company_id?: string | null
  name: string
  website: string | null
  industry: string | null
  career_url: string | null
  source: 'mapping' | 'search' | 'failed' | 'skipped'
  error?: string | null
}

/** 批量探测任务结果项（type=probe_batch） */
export interface BatchProbeItem {
  company_id: string
  name: string | null
  status: '成功' | '需人工' | 'skipped' | 'failed'
  career_url?: string | null
  error?: string | null
}

export interface BatchProbeResult {
  results: BatchProbeItem[]
  ok: number
  manual: number
  failed: number
  skipped: number
  total: number
}

/** 同步批量导入结果（POST /api/companies/import，resolve=false） */
export interface CompanyImportSyncResult {
  added: number
  skipped: number
  skipped_names: string[]
}

export interface ProbeCandidate {
  url: string
  confidence: 'high' | 'medium' | 'low'
  source: string
  reason: string
}

export interface FetchTaskResult {
  ats_type?: string | null
  career_url?: string | null
  job_candidates?: JobCandidate[]
  count?: number
}

export interface TaskResult {
  job_id: string
  type: string
  status: 'queued' | 'running' | 'done' | 'failed'
  progress: string | null
  result:
    | (({ candidates?: ProbeCandidate[] } & FetchTaskResult) & { results?: CompanyResolveResult[] })
    | null
  error: { code: string; message: string } | null
  queue_length?: number
  created_at: string
}

export interface Stats {
  total_applied: number
  active: number
  offered: number
  rejected: number
  pending_followup: number
  funnel: { status: string; count: number }[]
  channel_dist: { channel: string; count: number }[]
  weekly_trend: { week_start: string; count: number }[]
}

export interface BackupData {
  schema_version: number
  exported_at: string
  jobs: Job[]
  companies: Company[]
  resumes: Resume[]
}

export interface ImportBackupResult {
  mode: string
  jobs_added: number
  jobs_skipped: number
  companies_added: number
  resumes_added: number
  errors: { type: string; id: string; reason: string }[]
}
