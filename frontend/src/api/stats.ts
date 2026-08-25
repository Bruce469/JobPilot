import http from './http'
import type { Stats } from '@/types'

export function getStats(): Promise<Stats> {
  return http.get<Stats>('/stats').then((r) => r.data)
}
