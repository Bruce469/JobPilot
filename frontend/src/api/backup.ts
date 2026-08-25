import http from './http'
import type { BackupData, ImportBackupResult } from '@/types'

export function exportBackup(): Promise<BackupData> {
  return http.get<BackupData>('/backup/export').then((r) => r.data)
}

export function importBackup(payload: {
  schema_version: number
  mode: 'merge' | 'overwrite'
  jobs: unknown[]
  companies: unknown[]
  resumes: unknown[]
}): Promise<ImportBackupResult> {
  return http.post<ImportBackupResult>('/backup/import', payload).then((r) => r.data)
}
