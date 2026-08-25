import http from './http'
import type { TaskResult } from '@/types'

export function getTask(jobId: string): Promise<TaskResult> {
  return http.get<TaskResult>(`/tasks/${jobId}`).then((r) => r.data)
}
