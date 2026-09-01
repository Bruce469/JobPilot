// 公司库 store：CRUD + resolve 异步任务轮询
import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  batchDeleteCompanies,
  batchResolveCompanies,
  createCompany as apiCreateCompany,
  deleteCompany as apiDeleteCompany,
  importCompanies as apiImportCompanies,
  listCompanies,
  resolveCompany as apiResolveCompany,
  resolveCompanyName as apiResolveName,
  updateCompany as apiUpdateCompany,
} from '@/api/companies'
import type { ImportCompaniesResult } from '@/api/companies'
import type { CompanyFilters } from '@/api/companies'
import { getCompanyFacets } from '@/api/companies'
import { getTask } from '@/api/tasks'
import { ApiError } from '@/api/http'
import type { Company, CompanyFacets, CompanyImportRow, CompanyPayload, CompanyResolveResult, TaskResult } from '@/types'

export const useCompaniesStore = defineStore('companies', () => {
  const items = ref<Company[]>([])
  const loading = ref(false)
  // 公司库筛选候选池（DB distinct 值；城市/行业多选弹窗用）
  const facets = ref<CompanyFacets>({ cities: [], industries: [], natures: [] })
  // 会话内只拉一次，除非 force 主动刷新
  let facetsLoaded = false

  async function fetchFacets(force = false): Promise<CompanyFacets> {
    if (facetsLoaded && !force) return facets.value
    const data = await getCompanyFacets()
    facets.value = data
    facetsLoaded = true
    return facets.value
  }

  async function fetchCompanies(filters?: CompanyFilters) {
    loading.value = true
    try {
      const data = await listCompanies(filters)
      items.value = data.items
      return data
    } finally {
      loading.value = false
    }
  }

  function replace(c: Company) {
    const idx = items.value.findIndex((x) => x.id === c.id)
    if (idx >= 0) items.value[idx] = c
    else items.value.unshift(c)
  }

  async function createCompany(payload: CompanyPayload) {
    const c = await apiCreateCompany(payload)
    items.value.unshift(c)
    return c
  }

  async function updateCompany(id: string, payload: Partial<Company>) {
    const c = await apiUpdateCompany(id, payload)
    replace(c)
    return c
  }

  async function deleteCompany(id: string) {
    await apiDeleteCompany(id)
    items.value = items.value.filter((x) => x.id !== id)
  }

  /** 批量删除公司（岗位保留、解除关联），成功后本地移除 */
  async function batchDelete(ids: string[]): Promise<{ deleted: number }> {
    const res = await batchDeleteCompanies(ids)
    const gone = new Set(ids)
    items.value = items.value.filter((x) => !gone.has(x.id))
    return res
  }

  /** 批量补全已存公司（提交异步任务，进度由调用方轮询 pollTask） */
  async function batchResolve(ids: string[]): Promise<string> {
    const { job_id } = await batchResolveCompanies(ids)
    return job_id
  }

  /** 批量导入（结构化条目；resolve=true 返回 job_id 由组件轮询） */
  function importCompanies(rows: CompanyImportRow[], resolve?: boolean): Promise<ImportCompaniesResult> {
    return apiImportCompanies(rows, resolve)
  }

  /** 按名称查询补全（不落库） */
  function resolveName(name: string): Promise<CompanyResolveResult> {
    return apiResolveName(name)
  }

  /** 对已存公司补全（不落库） */
  function resolveCompany(id: string): Promise<CompanyResolveResult> {
    return apiResolveCompany(id)
  }

  /** 轮询任务直到 done/failed，超时上限默认 90s（后端单任务上限 60s）。onProgress 每轮回调进度。 */
  function pollTask(
    jobId: string,
    options?: { interval?: number; timeout?: number; onProgress?: (task: TaskResult) => void },
  ): Promise<TaskResult> {
    const interval = options?.interval ?? 1200
    const timeout = options?.timeout ?? 90000
    const start = Date.now()
    let timer: number | undefined
    return new Promise<TaskResult>((resolve, reject) => {
      const tick = async () => {
        try {
          const task = await getTask(jobId)
          options?.onProgress?.(task)
          if (task.status === 'done') {
            resolve(task)
            return
          }
          if (task.status === 'failed') {
            reject(
              new ApiError(
                task.error?.message || '任务失败',
                task.error?.code || 'TASK_FAILED',
                0,
                task.error ?? undefined,
              ),
            )
            return
          }
          if (Date.now() - start > timeout) {
            reject(new ApiError('任务超时，请稍后重试', 'TASK_TIMEOUT', 0))
            return
          }
          timer = window.setTimeout(tick, interval)
        } catch (e) {
          reject(e)
        }
      }
      void tick()
    }).finally(() => {
      if (timer !== undefined) window.clearTimeout(timer)
    })
  }

  return {
    items,
    loading,
    facets,
    fetchFacets,
    fetchCompanies,
    createCompany,
    updateCompany,
    deleteCompany,
    batchDelete,
    batchResolve,
    importCompanies,
    resolveName,
    resolveCompany,
    pollTask,
  }
})
