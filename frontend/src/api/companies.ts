import http from './http'
import type { Company, CompanyFacets, CompanyImportRow, CompanyImportSyncResult, CompanyPayload, CompanyResolveResult, Job } from '@/types'
import type { ListResult } from './jobs'

export interface CompanyFilters {
  /** 城市多值（发请求时逗号拼接为 `city=北京,深圳`，精确 IN 匹配）；空数组/undefined 不传 */
  city?: string[] | null
  /** 行业多值（发请求时逗号拼接为 `industry=互联网,能源`，精确 IN 匹配）；空数组/undefined 不传 */
  industry?: string[] | null
  nature?: string | null
  /** 处理状态：0=未处理 1=已处理；null/undefined 不筛 */
  processed?: number | null
  keyword?: string | null
}

export function listCompanies(filters?: CompanyFilters): Promise<ListResult<Company>> {
  const params: Record<string, string> = {}
  if (filters) {
    if (filters.city?.length) params.city = filters.city.join(',')
    if (filters.industry?.length) params.industry = filters.industry.join(',')
    if (filters.nature) params.nature = filters.nature
    if (filters.processed != null) params.processed = String(filters.processed)
    if (filters.keyword) params.keyword = filters.keyword
  }
  return http.get<ListResult<Company>>('/companies', { params }).then((r) => r.data)
}

/** 公司库筛选候选池：{cities, industries, natures} 各为 DISTINCT 非空值排序列表 */
export function getCompanyFacets(): Promise<CompanyFacets> {
  return http.get<CompanyFacets>('/companies/facets').then((r) => r.data)
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

/** 某公司的全部岗位（公司库展开列表数据源，GET /api/companies/{id}/jobs） */
export function listCompanyJobs(companyId: string): Promise<ListResult<Job>> {
  return http.get<ListResult<Job>>(`/companies/${companyId}/jobs`).then((r) => r.data)
}

export interface AsyncTaskRef {
  job_id: string
  type: string
}

/** 批量删除公司（POST /api/companies/batch-delete） */
export function batchDeleteCompanies(ids: string[]): Promise<{ deleted: number }> {
  return http.post<{ deleted: number }>('/companies/batch-delete', { ids }).then((r) => r.data)
}

/** 批量补全已存公司（POST /api/companies/batch-resolve，异步任务，结果自动写入缺失字段） */
export function batchResolveCompanies(ids: string[]): Promise<AsyncTaskRef> {
  return http.post<AsyncTaskRef>('/companies/batch-resolve', { ids }).then((r) => r.data)
}

/** 异步导入任务返回 { job_id }，与同步导入结果（{added, skipped, skipped_names}）用 job_id 存在与否区分 */
export type ImportCompaniesResult = CompanyImportSyncResult | { job_id: string }

/**
 * 批量导入公司（POST /api/companies/import）
 * - rows 为结构化条目（公司全称 + 可选 城市/行业/性质/官网）
 * - resolve=true：创建后异步批量补全缺失字段，返回 {job_id}，用 GET /api/tasks/{job_id} 轮询
 * - resolve=false：同步新增，返回 {added, skipped, skipped_names}
 */
export function importCompanies(rows: CompanyImportRow[], resolve?: boolean): Promise<ImportCompaniesResult> {
  return http
    .post<ImportCompaniesResult>('/companies/import', { companies: rows, resolve: resolve ?? true })
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
