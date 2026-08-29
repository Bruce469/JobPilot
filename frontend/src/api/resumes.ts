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

/**
 * 上传 PDF 生成结构化简历（multipart 字段 file，仅 .pdf / ≤10MB，否则 400）。
 * 成功后返回完整 Resume（含 pdf_file）；FormData 交给 axios 自动设置 multipart 边界，勿手动覆盖 Content-Type。
 */
export function uploadResumePdf(file: File): Promise<Resume> {
  const form = new FormData()
  form.append('file', file)
  return http.post<Resume>('/resumes/upload-pdf', form).then((r) => r.data)
}

/** 下载简历源 PDF 字节流（鉴权依赖 X-Auth-Token 请求头，axios 实例自动注入） */
export function getResumePdfBlob(id: string): Promise<Blob> {
  return http.get<Blob>(`/resumes/${id}/pdf`, { responseType: 'blob' }).then((r) => r.data)
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
