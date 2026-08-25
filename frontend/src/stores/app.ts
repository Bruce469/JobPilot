// 应用级状态：boot / token / schema_version / 备份提醒
import { defineStore } from 'pinia'
import { fetchBoot } from '@/api/boot'
import { setToken } from '@/api/http'
import type { BootBackup } from '@/api/boot'

export const useAppStore = defineStore('app', {
  state: () => ({
    booted: false,
    booting: false,
    bootError: '' as string,
    schemaVersion: 0,
    appName: '秋招投递助手',
    appVersion: '0.1.0',
    backup: { last_exported_at: null as string | null, days_since: null as number | null, need_backup: false },
    backupAlertDismissed: sessionStorage.getItem('backup_alert_dismissed') === '1',
  }),
  getters: {
    backendOnline: (state) => state.booted,
  },
  actions: {
    async boot() {
      this.booting = true
      this.bootError = ''
      try {
        const data = await fetchBoot()
        setToken(data.token)
        this.schemaVersion = data.schema_version
        if (data.app?.name) this.appName = data.app.name
        if (data.app?.version) this.appVersion = data.app.version
        this.backup = data.backup ?? (this.backup as BootBackup)
        this.booted = true
      } catch (e) {
        this.booted = false
        this.bootError = e instanceof Error ? e.message : '无法连接后端服务'
      } finally {
        this.booting = false
      }
    },
    dismissBackupAlert() {
      this.backupAlertDismissed = true
      sessionStorage.setItem('backup_alert_dismissed', '1')
    },
  },
})
