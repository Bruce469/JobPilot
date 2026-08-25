<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { getToken } from '@/api/http'
import { exportBackup, importBackup } from '@/api/backup'
import { downloadJson } from '@/utils/download'
import { todayStr } from '@/utils/date'
import { useJobsStore } from '@/stores/jobs'
import { useCompaniesStore } from '@/stores/companies'
import { useResumesStore } from '@/stores/resumes'
import type { BackupData, ImportBackupResult } from '@/types'

const appStore = useAppStore()
const jobsStore = useJobsStore()
const companiesStore = useCompaniesStore()
const resumesStore = useResumesStore()

const exporting = ref(false)
const importing = ref(false)

// ---------------- 导出 ----------------
async function onExport() {
  exporting.value = true
  try {
    const data = await exportBackup()
    downloadJson(`秋招投递助手-备份-${todayStr()}.json`, data)
    ElMessage.success('备份已导出')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '导出失败')
  } finally {
    exporting.value = false
  }
}

// ---------------- 导入 ----------------
const fileInput = ref<HTMLInputElement>()
const selectedFile = ref<{ name: string; data: BackupData } | null>(null)
const parseError = ref('')
const mode = ref<'merge' | 'overwrite'>('merge')
const importResult = ref<ImportBackupResult | null>(null)

function pickFile() {
  fileInput.value?.click()
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  parseError.value = ''
  importResult.value = null
  selectedFile.value = null
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    try {
      const raw: unknown = JSON.parse(String(reader.result))
      const check = validateBackup(raw)
      if (!check.ok) {
        parseError.value = check.message
        return
      }
      selectedFile.value = { name: file.name, data: check.data }
      // schema_version 提示
      const cur = appStore.schemaVersion
      if (check.data.schema_version > cur) {
        parseError.value = `备份文件版本（${check.data.schema_version}）高于当前支持版本（${cur}），请升级后再导入`
      } else {
        ElMessage.success(`解析成功：${check.data.jobs.length} 条岗位 / ${check.data.companies.length} 家公司 / ${check.data.resumes.length} 份简历`)
      }
    } catch {
      parseError.value = '文件格式不正确：不是合法的 JSON'
    }
  }
  reader.onerror = () => {
    parseError.value = '文件读取失败'
  }
  reader.readAsText(file)
}

function validateBackup(raw: unknown): { ok: true; data: BackupData } | { ok: false; message: string } {
  if (typeof raw !== 'object' || raw === null) return { ok: false, message: '文件格式不正确：不是 JSON 对象' }
  const d = raw as Record<string, unknown>
  if (typeof d.schema_version !== 'number') return { ok: false, message: '文件格式不正确：缺少 schema_version 字段' }
  if (!Array.isArray(d.jobs) || !Array.isArray(d.companies) || !Array.isArray(d.resumes)) {
    return { ok: false, message: '文件格式不正确：缺少 jobs/companies/resumes 数组' }
  }
  return { ok: true, data: raw as unknown as BackupData }
}

async function onImport() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择备份文件')
    return
  }
  const data = selectedFile.value.data
  if (data.schema_version > appStore.schemaVersion) {
    ElMessage.error('备份文件版本过高，拒绝导入')
    return
  }
  if (mode.value === 'overwrite') {
    try {
      await ElMessageBox.confirm(
        '覆盖模式将用备份数据全量替换现有数据（岗位/公司/简历），现有数据将被清空重建。确定继续？',
        '覆盖导入确认',
        {
          type: 'warning',
          confirmButtonText: '确定覆盖',
          cancelButtonText: '取消',
        },
      )
    } catch {
      return
    }
  }
  importing.value = true
  try {
    const res = await importBackup({
      schema_version: data.schema_version,
      mode: mode.value,
      jobs: data.jobs,
      companies: data.companies,
      resumes: data.resumes,
    })
    importResult.value = res
    ElMessage.success('导入完成')
    // 刷新各 store，保持当前会话数据一致
    await Promise.all([
      jobsStore.fetchJobs({ include_ended: true }).catch(() => undefined),
      companiesStore.fetchCompanies().catch(() => undefined),
      resumesStore.fetchResumes().catch(() => undefined),
    ])
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '导入失败')
  } finally {
    importing.value = false
  }
}

const maskedToken = (token: string | null) => {
  if (!token) return '未获取'
  if (token.length <= 10) return token.slice(0, 4) + '***'
  return `${token.slice(0, 6)}...${token.slice(-4)}`
}
</script>

<template>
  <div class="settings-page">
    <!-- 备份 -->
    <el-card shadow="never" class="settings-card">
      <template #header>
        <span>数据备份</span>
      </template>
      <div class="backup-row">
        <div class="backup-info">
          <p class="info-line">
            一键导出全部数据（岗位 / 公司 / 简历），文件含 schema_version，用于换设备迁移与防误删。
          </p>
          <p v-if="appStore.backup.need_backup && !appStore.backupAlertDismissed" class="info-warn">
            距上次导出已 {{ appStore.backup.days_since ?? '?' }} 天，建议尽快备份。
          </p>
          <p class="info-muted">
            上次导出：{{ appStore.backup.last_exported_at || '从未导出' }}
          </p>
        </div>
        <el-button type="primary" :loading="exporting" @click="onExport">导出 JSON</el-button>
      </div>
    </el-card>

    <!-- 导入 -->
    <el-card shadow="never" class="settings-card">
      <template #header>
        <span>导入备份</span>
      </template>
      <input ref="fileInput" type="file" accept=".json,application/json" class="hidden-input" @change="onFileChange" />
      <div class="import-row">
        <div class="import-info">
          <p class="info-muted">选择备份 JSON 文件，选择导入模式后执行。</p>
          <p class="info-muted">
            合并模式：同 id 以本机数据为准，备份中的新记录被添加；覆盖模式：全量替换（需二次确认）。
          </p>
        </div>
        <el-button :disabled="!!selectedFile" @click="pickFile">选择文件</el-button>
      </div>

      <div v-if="parseError" class="parse-error">{{ parseError }}</div>

      <div v-if="selectedFile" class="selected-file">
        <el-tag type="success" effect="light">{{ selectedFile.name }}</el-tag>
        <div class="file-summary">
          版本 {{ selectedFile.data.schema_version }} · 岗位 {{ selectedFile.data.jobs.length }} · 公司
          {{ selectedFile.data.companies.length }} · 简历 {{ selectedFile.data.resumes.length }} · 导出于
          {{ selectedFile.data.exported_at }}
        </div>
      </div>

      <div v-if="selectedFile" class="import-actions">
        <el-radio-group v-model="mode">
          <el-radio value="merge">合并模式（默认）</el-radio>
          <el-radio value="overwrite">覆盖模式</el-radio>
        </el-radio-group>
        <el-button type="primary" :loading="importing" @click="onImport">开始导入</el-button>
      </div>

      <div v-if="importResult" class="import-result">
        <el-alert
          type="success"
          :closable="false"
          :title="`导入完成（${importResult.mode}）：新增岗位 ${importResult.jobs_added}、跳过 ${importResult.jobs_skipped}、新增公司 ${importResult.companies_added}、新增简历 ${importResult.resumes_added}`"
        />
        <div v-if="importResult.errors.length" class="import-errors">
          <div v-for="(err, i) in importResult.errors" :key="i" class="import-error">
            {{ err.type }}[{{ err.id }}]：{{ err.reason }}
          </div>
        </div>
      </div>
    </el-card>

    <!-- 系统信息 -->
    <el-card shadow="never" class="settings-card">
      <template #header>
        <span>系统信息</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="应用">{{ appStore.appName }} v{{ appStore.appVersion }}</el-descriptions-item>
        <el-descriptions-item label="Schema 版本">{{ appStore.schemaVersion }}</el-descriptions-item>
        <el-descriptions-item label="Token">
          <el-tooltip content="实际值仅存内存/sessionStorage，页面关闭即失效" placement="top">
            <span class="mono">{{ maskedToken(getToken()) }}</span>
          </el-tooltip>
        </el-descriptions-item>
        <el-descriptions-item label="后端地址">http://127.0.0.1:8000（/api 经 Vite proxy 转发）</el-descriptions-item>
      </el-descriptions>
      <p class="info-muted token-tip">
        Token 由后端启动时随机生成，经 /api/boot 下发后保存在浏览器 sessionStorage，页面关闭即失效。
      </p>
    </el-card>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 860px;
  margin: 0 auto;
}
.settings-card {
  margin-bottom: 16px;
}
.backup-row,
.import-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.info-line {
  margin: 0 0 6px;
  font-size: 13px;
  color: #374151;
}
.info-warn {
  margin: 0 0 6px;
  font-size: 12px;
  color: #b45309;
}
.info-muted {
  margin: 0;
  font-size: 12px;
  color: #9ca3af;
}
.hidden-input {
  display: none;
}
.parse-error {
  margin-top: 12px;
  color: #dc2626;
  font-size: 13px;
  background: #feecec;
  border-radius: 6px;
  padding: 8px 12px;
}
.selected-file {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.file-summary {
  font-size: 12px;
  color: #6b7280;
}
.import-actions {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 16px;
}
.import-result {
  margin-top: 12px;
}
.import-errors {
  margin-top: 8px;
  font-size: 12px;
  color: #b91c1c;
}
.import-error {
  margin-bottom: 2px;
}
.mono {
  font-family: monospace;
}
.token-tip {
  margin-top: 10px;
}
</style>
