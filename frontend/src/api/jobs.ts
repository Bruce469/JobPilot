import http from './http'
import type { Job, JobCandidate, JobEvent, JobDetail } from '@/types'

export interface ListResult<T> {
  items: T[]
  total: number
}

export interface JobFilters {
  status?: string[] | null
  company?: string | null
  city?: string | null
  industry?: string | null
  channel?: string | null
  keyword?: string | null
  include_ended?: boolean
  sort?: string
  sort_dir?: 'asc' | 'desc'
}

export interface JobPayload {
  company?: string
  company_id?: string | null
  position?: string | null
  job_type?: string | null
  degree?: string | null
  city?: string | null
  industry?: string | null
  channel?: string | null
  job_url?: string | null
  source_job_id?: string | null
  publish_date?: string | null
  deadline?: string | null
  resume_id?: string | null
}

export interface StatusChangeEvent {
  id: string
  job_id: string
  time: string
  type: string
  from_status: string | null
  to_status: string | null
  note: string | null
  created_at: string
}

export interface StatusChangeResult {
  job: Job
  event: StatusChangeEvent | null
}

export interface ImportResult {
  added: number
  skipped: number
  failed: number
  added_ids: string[]
  failures: { index: number; reason: string }[]
}

export function listJobs(filters: JobFilters = {}): Promise<ListResult<Job>> {
  const params: Record<string, string> = {}
  if (filters.status?.length) params.status = filters.status.join(',')
  if (filters.company) params.company = filters.company
  if (filters.city) params.city = filters.city
  if (filters.industry) params.industry = filters.industry
  if (filters.channel) params.channel = filters.channel
  if (filters.keyword) params.keyword = filters.keyword
  if (filters.include_ended) params.include_ended = 'true'
  params.sort = filters.sort || 'updated_at'
  params.sort_dir = filters.sort_dir || 'desc'
  return http.get<ListResult<Job>>('/jobs', { params }).then((r) => r.data)
}

export function createJob(payload: JobPayload): Promise<Job> {
  return http.post<Job>('/jobs', payload).then((r) => r.data)
}

export function getJobDetail(id: string): Promise<JobDetail> {
  return http.get<JobDetail>(`/jobs/${id}`).then((r) => r.data)
}

export function updateJob(id: string, payload: JobPayload): Promise<Job> {
  return http.put<Job>(`/jobs/${id}`, payload).then((r) => r.data)
}

export function deleteJob(id: string): Promise<void> {
  return http.delete(`/jobs/${id}`).then(() => undefined)
}

export function batchDeleteJobs(ids: string[]): Promise<{ deleted: number }> {
  return http.post<{ deleted: number }>('/jobs/batch-delete', { ids }).then((r) => r.data)
}

export function changeJobStatus(id: string, status: string, note?: string, time?: string): Promise<StatusChangeResult> {
  const body: Record<string, string> = { status }
  if (note) body.note = note
  if (time) body.time = time
  return http.post<StatusChangeResult>(`/jobs/${id}/status`, body).then((r) => r.data)
}

export function importJobs(companyId: string, jobs: JobCandidate[]): Promise<ImportResult> {
  return http.post<ImportResult>('/jobs/import', { company_id: companyId, jobs }).then((r) => r.data)
}

export type { JobEvent }
