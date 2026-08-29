// 简历 store：CRUD（删除引用保护）
import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  createResume as apiCreateResume,
  deleteResume as apiDeleteResume,
  listResumes,
  updateResume as apiUpdateResume,
} from '@/api/resumes'
import type { DeleteResumeResult } from '@/api/resumes'
import type { Resume, ResumePayload } from '@/types'

export const useResumesStore = defineStore('resumes', () => {
  const items = ref<Resume[]>([])
  const loading = ref(false)

  async function fetchResumes() {
    loading.value = true
    try {
      const data = await listResumes()
      items.value = data.items
      return data
    } finally {
      loading.value = false
    }
  }

  async function createResume(payload: ResumePayload) {
    const r = await apiCreateResume(payload)
    items.value.unshift(r)
    return r
  }

  async function updateResume(id: string, payload: Partial<ResumePayload>) {
    const r = await apiUpdateResume(id, payload)
    const idx = items.value.findIndex((x) => x.id === id)
    if (idx >= 0) items.value[idx] = r
    return r
  }

  /** 返回 undefined 表示已删除；返回 {referenced_by} 表示被引用需要二次确认 */
  async function deleteResume(id: string, force = false): Promise<DeleteResumeResult | undefined> {
    const result = await apiDeleteResume(id, force)
    // axios 对 204 空响应返回 '' 或 undefined（视版本而定），统一用 falsy 判断
    if (!result || result.deleted) {
      items.value = items.value.filter((x) => x.id !== id)
      return undefined
    }
    return result
  }

  return { items, loading, fetchResumes, createResume, updateResume, deleteResume }
})
