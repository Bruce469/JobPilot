import http from './http'
import type { Company, CompanyImportSyncResult, CompanyPayload, CompanyResolveResult } from '@/types'
import type { ListResult } from './jobs'

export function listCompanies(): Promise<ListResult<Company>> {
  return http.get<ListResult<Company>>('/companies').then((r) => r.data)
}

export function createCompany(payload: CompanyPayload): Promise<Company> {
  return http.post<Company>('/companies', payload).then((r) => r.data)
}

export function updateCompany(id: string, payload: Partial<Company>): Promise<Company> {
  return http.put<Company>(`/companies/${id}`, payload).then((r) => r.data)
}

export function deleteCompany(id: string): Promise<void> {
  return http.delete(`/companies/${id}`).then(() => undefined)
}

export interface AsyncTaskRef {
  job_id: string
  type: 'probe' | 'fetch' | 'probe_batch' | 'resolve'
}

export function probeCompany(id: string): Promise<AsyncTaskRef> {
  return http.post<AsyncTaskRef>(`/companies/${id}/probe`).then((r) => r.data)
}

export function fetchCompanyJobs(id: string, careerUrl?: string): Promise<AsyncTaskRef> {
  const body = careerUrl ? { career_url: careerUrl } : {}
  return http.post<AsyncTaskRef>(`/companies/${id}/fetch`, body).then((r) => r.data)
}

/** 批量删除公司（POST /api/companies/batch-delete） */
export function batchDeleteCompanies(ids: string[]): Promise<{ deleted: number }> {
  return http.post<{ deleted: number }>('/companies/batch-delete', { ids }).then((r) => r.data)
}

/** 批量探测招聘页（POST /api/companies/batch-probe，异步任务） */
export function batchProbeCompanies(ids: string[]): Promise<AsyncTaskRef> {
  return http.post<AsyncTaskRef>('/companies/batch-probe', { ids }).then((r) => r.data)
}

/** 批量补全已存公司（POST /api/companies/batch-resolve，异步任务，结果自动写入缺失字段） */
export function batchResolveCompanies(ids: string[]): Promise<AsyncTaskRef> {
  return http.post<AsyncTaskRef>('/companies/batch-resolve', { ids }).then((r) => r.data)
}

/** 异步导入任务返回 { job_id }，与同步导入结果（{added, skipped, skipped_names}）用 job_id 存在与否区分 */
export type ImportCompaniesResult = CompanyImportSyncResult | { job_id: string }

/**
 * 批量导入公司（POST /api/companies/import）
 * - resolve=false：同步新增，返回 {added, skipped, skipped_names}
 * - resolve=true：异步批量补全，返回 {job_id}，用 GET /api/tasks/{job_id} 轮询
 */
export function importCompanies(names: string[], resolve?: boolean): Promise<ImportCompaniesResult> {
  return http
    .post<ImportCompaniesResult>('/companies/import', { names, resolve: resolve ?? true })
    .then((r) => r.data)
}

/** 仅按名称查询补全（POST /api/companies/resolve，不落库） */
export function resolveCompanyName(name: string): Promise<CompanyResolveResult> {
  return http.post<CompanyResolveResult>('/companies/resolve', { name }).then((r) => r.data)
}

/** 对已存公司执行补全（POST /api/companies/{id}/resolve，不落库，需人工确认后保存） */
export function resolveCompany(id: string): Promise<CompanyResolveResult> {
  return http.post<CompanyResolveResult>(`/companies/${id}/resolve`).then((r) => r.data)
}
