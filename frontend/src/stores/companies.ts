// 公司库 store：CRUD + probe/fetch 异步任务轮询
import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import {
  batchDeleteCompanies,
  batchProbeCompanies,
  batchResolveCompanies,
  createCompany as apiCreateCompany,
  deleteCompany as apiDeleteCompany,
  fetchCompanyJobs as apiFetchCompanyJobs,
  importCompanies as apiImportCompanies,
  listCompanies,
  probeCompany as apiProbeCompany,
  resolveCompany as apiResolveCompany,
  resolveCompanyName as apiResolveName,
  updateCompany as apiUpdateCompany,
} from '@/api/companies'
import type { ImportCompaniesResult } from '@/api/companies'
import type { CompanyFilters } from '@/api/companies'
import { getTask } from '@/api/tasks'
import { ApiError } from '@/api/http'
import type { Company, CompanyPayload, CompanyResolveResult, TaskResult } from '@/types'

export const useCompaniesStore = defineStore('companies', () => {
  const items = ref<Company[]>([])
  const loading = ref(false)
  // 进行中的任务状态（companyId -> 任务类型/进度文本）
  const running = reactive<Record<string, { type: 'probe' | 'fetch'; jobId: string }>>({})

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
    delete running[id]
  }

  /** 批量删除公司（岗位保留、解除关联），成功后本地移除 */
  async function batchDelete(ids: string[]): Promise<{ deleted: number }> {
    const res = await batchDeleteCompanies(ids)
    const gone = new Set(ids)
    items.value = items.value.filter((x) => !gone.has(x.id))
    ids.forEach((id) => delete running[id])
    return res
  }

  /** 批量探测招聘页（提交异步任务，进度由调用方轮询 pollTask） */
  async function batchProbe(ids: string[]): Promise<string> {
    const { job_id } = await batchProbeCompanies(ids)
    return job_id
  }

  /** 批量补全已存公司（提交异步任务，进度由调用方轮询 pollTask） */
  async function batchResolve(ids: string[]): Promise<string> {
    const { job_id } = await batchResolveCompanies(ids)
    return job_id
  }

  async function probe(id: string): Promise<string> {
    const { job_id } = await apiProbeCompany(id)
    running[id] = { type: 'probe', jobId: job_id }
    return job_id
  }

  async function fetchJobs(id: string, careerUrl?: string): Promise<string> {
    const { job_id } = await apiFetchCompanyJobs(id, careerUrl)
    running[id] = { type: 'fetch', jobId: job_id }
    return job_id
  }

  /** 批量导入（resolve=false 同步新增 / resolve=true 返回 job_id 由组件轮询） */
  function importCompanies(names: string[], resolve?: boolean): Promise<ImportCompaniesResult> {
    return apiImportCompanies(names, resolve)
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
    running,
    fetchCompanies,
    createCompany,
    updateCompany,
    deleteCompany,
    batchDelete,
    batchProbe,
    batchResolve,
    probe,
    fetchJobs,
    importCompanies,
    resolveName,
    resolveCompany,
    pollTask,
  }
})
