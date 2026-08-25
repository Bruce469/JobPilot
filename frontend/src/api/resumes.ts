import http from './http'
import type { Resume, ResumePayload } from '@/types'
import type { ListResult } from './jobs'

export function listResumes(): Promise<ListResult<Resume>> {
  return http.get<ListResult<Resume>>('/resumes').then((r) => r.data)
}

export function getResume(id: string): Promise<Resume> {
  return http.get<Resume>(`/resumes/${id}`).then((r) => r.data)
}

export function createResume(payload: ResumePayload): Promise<Resume> {
  return http.post<Resume>('/resumes', payload).then((r) => r.data)
}

export function updateResume(id: string, payload: Partial<ResumePayload>): Promise<Resume> {
  return http.put<Resume>(`/resumes/${id}`, payload).then((r) => r.data)
}

export interface DeleteResumeResult {
  referenced_by: number
  deleted: boolean
}

/** 未 force 且被引用时返回 {referenced_by, deleted:false}；否则 204 返回 undefined */
export function deleteResume(id: string, force = false): Promise<DeleteResumeResult | undefined> {
  return http
    .delete<DeleteResumeResult>(`/resumes/${id}`, { params: force ? { force: 'true' } : {} })
    .then((r) => r.data)
}
