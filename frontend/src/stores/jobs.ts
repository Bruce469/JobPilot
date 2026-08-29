// 岗位 store：列表 / 筛选 / CRUD / 状态流转 / 事件缓存
import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import {
  batchDeleteJobs,
  changeJobStatus,
  createJob as apiCreateJob,
  deleteJob as apiDeleteJob,
  getJobDetail,
  importJobs as apiImportJobs,
  listJobs,
  updateJob as apiUpdateJob,
} from '@/api/jobs'
import type { JobFilters, JobPayload, ImportResult } from '@/api/jobs'
import type { Job, JobCandidate, JobEvent } from '@/types'
import { isActive } from '@/utils/normalize'

export const useJobsStore = defineStore('jobs', () => {
  const items = ref<Job[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref('')
  // 事件时间线缓存（列表接口不含 events，详情接口按需拉取后缓存）
  const eventsByJob = reactive<Record<string, JobEvent[]>>({})

  async function fetchJobs(filters: JobFilters = {}) {
    loading.value = true
    error.value = ''
    try {
      const data = await listJobs(filters)
      items.value = data.items
      total.value = data.total
      return data
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载岗位失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  function replaceJob(job: Job) {
    const idx = items.value.findIndex((j) => j.id === job.id)
    if (idx >= 0) items.value[idx] = job
    else items.value.unshift(job)
  }

  function removeJobs(ids: string[]) {
    const set = new Set(ids)
    items.value = items.value.filter((j) => !set.has(j.id))
    for (const id of ids) delete eventsByJob[id]
  }

  async function createJob(payload: JobPayload) {
    const job = await apiCreateJob(payload)
    items.value.unshift(job)
    total.value += 1
    return job
  }

  async function updateJob(id: string, payload: JobPayload) {
    const job = await apiUpdateJob(id, payload)
    replaceJob(job)
    return job
  }

  async function deleteJob(id: string) {
    await apiDeleteJob(id)
    removeJobs([id])
    total.value = Math.max(0, total.value - 1)
  }

  async function batchDelete(ids: string[]) {
    const res = await batchDeleteJobs(ids)
    removeJobs(ids)
    total.value = Math.max(0, total.value - res.deleted)
    return res
  }

  /**
   * 状态流转（拖拽与按钮共用）。成功后用返回的 job 就地更新、事件追加到缓存。
   * nextTime/failStage 透传给后端（仅对应目标状态生效，见 changeJobStatus）。
   */
  async function changeStatus(id: string, status: string, note?: string, time?: string, nextTime?: string | null, failStage?: string | null) {
    const res = await changeJobStatus(id, status, note, time, nextTime, failStage)
    if (res.job) replaceJob(res.job)
    if (res.event) {
      eventsByJob[id] = [...(eventsByJob[id] ?? []), res.event]
    }
    return res
  }

  async function importJobs(companyId: string, candidates: JobCandidate[]): Promise<ImportResult> {
    return apiImportJobs(companyId, candidates)
  }

  async function loadDetail(id: string) {
    const detail = await getJobDetail(id)
    eventsByJob[id] = detail.events ?? []
    return detail
  }

  /** 并发受限地拉取一批岗位的事件（看板/列表的提醒区使用），已有缓存则跳过 */
  async function loadEvents(ids: string[]) {
    const queue = ids.filter((id) => !eventsByJob[id])
    const concurrency = 8
    if (!queue.length) return
    const workers = Array.from({ length: Math.min(concurrency, queue.length) }, async () => {
      while (queue.length) {
        const id = queue.shift() as string
        try {
          await loadDetail(id)
        } catch {
          // 单条失败不影响其余
        }
      }
    })
    await Promise.all(workers)
  }

  /** 拉取所有进行中岗位的事件（供看板「今日/本周安排」） */
  async function loadActiveEvents() {
    const ids = items.value.filter((j) => isActive(j.status)).map((j) => j.id)
    if (ids.length) await loadEvents(ids)
  }

  return {
    items,
    total,
    loading,
    error,
    eventsByJob,
    fetchJobs,
    createJob,
    updateJob,
    deleteJob,
    batchDelete,
    changeStatus,
    importJobs,
    loadDetail,
    loadEvents,
    loadActiveEvents,
  }
})
