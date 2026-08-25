import http from './http'

export interface BootBackup {
  last_exported_at: string | null
  days_since: number | null
  need_backup: boolean
}

export interface BootData {
  token: string
  schema_version: number
  app: { name: string; version: string }
  backup: BootBackup
}

export function fetchBoot(): Promise<BootData> {
  return http.get<BootData>('/boot').then((r) => r.data)
}
