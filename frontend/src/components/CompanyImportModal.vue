<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useCompaniesStore } from '@/stores/companies'
import type { CompanyImportSyncResult, CompanyResolveResult } from '@/types'
import { decodeTxtBuffer, parseTxtLines } from '@/utils/txt'

const props = defineProps<{ modelValue: boolean }>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'imported'): void
}>()

const companiesStore = useCompaniesStore()

const PREVIEW_LIMIT = 100

// ---------------- 状态 ----------------
type Step = 'pick' | 'preview' | 'running' | 'result'
const step = ref<Step>('pick')
const fileInput = ref<HTMLInputElement | null>(null)
const fileName = ref('')
const names = ref<string[]>([])
const resolveOnImport = ref(true)

const submitting = ref(false)
const progress = ref<{ done: number; total: number } | null>(null)
const progressText = ref('')

const syncResult = ref<CompanyImportSyncResult | null>(null)
const asyncResult = ref<{ ok: number; skipped: number; failed: CompanyResolveResult[] } | null>(null)

watch(
  () => props.modelValue,
  (v) => {
    if (!v) return
    step.value = 'pick'
    fileName.value = ''
    names.value = []
    resolveOnImport.value = true
    submitting.value = false
    progress.value = null
    progressText.value = ''
    syncResult.value = null
    asyncResult.value = null
  },
)

// ---------------- 文件读取与解析 ----------------
function openFilePicker() {
  fileInput.value?.click()
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  fileName.value = file.name
  const reader = new FileReader()
  reader.onload = () => {
    try {
      const text = decodeTxtBuffer(reader.result as ArrayBuffer)
      names.value = parseTxtLines(text)
      if (!names.value.length) {
        ElMessage.warning('文件中未解析到公司名，请确认每行一个公司名')
        step.value = 'pick'
        return
      }
      step.value = 'preview'
    } catch {
      ElMessage.error('文件解析失败，请确认是 UTF-8 或 GBK 编码的 txt 文件')
      step.value = 'pick'
    }
  }
  reader.onerror = () => {
    ElMessage.error('文件读取失败')
  }
  reader.readAsArrayBuffer(file)
  input.value = ''
}

const previewNames = computed(() => names.value.slice(0, PREVIEW_LIMIT))
const previewHint = computed(() =>
  names.value.length > PREVIEW_LIMIT ? `共解析到 ${names.value.length} 条，预览前 ${PREVIEW_LIMIT} 条` : `共解析到 ${names.value.length} 条`,
)

// ---------------- 导入提交与轮询 ----------------
/** 解析任务进度文本末尾的「x/y」（如「已补全 3/105」）；无法解析时返回 null（用于不确定进度条） */
function parseProgress(p: string | null): { done: number; total: number } | null {
  if (!p) return null
  const m = p.match(/(\d+)\s*\/\s*(\d+)\s*$/)
  if (m) return { done: Number(m[1]), total: Number(m[2]) }
  return null
}

const percent = computed(() => {
  const p = progress.value
  if (!p || p.total <= 0) return 0
  return Math.round((p.done / p.total) * 100)
})

async function onConfirm() {
  if (!names.value.length) return
  submitting.value = true
  try {
    const res = await companiesStore.importCompanies(names.value, resolveOnImport.value)
    if ('job_id' in res) {
      // 异步批量补全：轮询任务
      step.value = 'running'
      progress.value = null
      progressText.value = '排队中'
      const task = await companiesStore.pollTask(res.job_id, {
        interval: 1200,
        timeout: 5 * 60 * 1000,
        onProgress: (t) => {
          progress.value = parseProgress(t.progress)
          progressText.value = t.progress ?? ''
        },
      })
      const details = task.result?.results ?? []
      const ok = details.filter((d) => d.source !== 'failed' && d.source !== 'skipped').length
      const skipped = details.filter((d) => d.source === 'skipped').length
      const failed = details.filter((d) => d.source === 'failed')
      asyncResult.value = { ok, skipped, failed }
      step.value = 'result'
      if (failed.length) ElMessage.warning(`补全完成：成功 ${ok} 家，失败 ${failed.length} 家${skipped ? `，跳过 ${skipped} 家` : ''}`)
      else ElMessage.success(`补全完成：成功 ${ok} 家${skipped ? `，跳过 ${skipped} 家` : ''}`)
    } else {
      syncResult.value = res
      step.value = 'result'
      ElMessage.success(`导入完成：新增 ${res.added} 家，跳过 ${res.skipped} 家`)
    }
    emit('imported')
  } catch (e) {
    if (step.value === 'running') step.value = 'preview'
    ElMessage.error(e instanceof Error ? e.message : '导入失败')
  } finally {
    submitting.value = false
  }
}

const failedDetails = computed(() => asyncResult.value?.failed ?? [])

function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="导入公司（txt）"
    width="560px"
    :close-on-click-modal="false"
    :close-on-press-escape="!submitting"
    :show-close="!submitting"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <input ref="fileInput" type="file" accept=".txt,text/plain" hidden @change="onFileChange" />

    <!-- 步骤一：选择文件 -->
    <div v-if="step === 'pick'" class="pick-box">
      <p class="hint">支持 UTF-8 / GBK 编码的 txt 文件，每行一个公司名；自动忽略空行、去重、跳过已存在公司。</p>
      <div class="pick-action">
        <el-button type="primary" plain @click="openFilePicker">选择 txt 文件</el-button>
      </div>
    </div>

    <!-- 步骤二：预览 -->
    <div v-else-if="step === 'preview'">
      <div class="preview-summary">
        <span class="file-name">{{ fileName }}</span>
        <span class="preview-hint">{{ previewHint }}</span>
      </div>
      <div class="name-list">
        <div v-for="(n, i) in previewNames" :key="i" class="name-item">{{ n }}</div>
        <div v-if="names.length > PREVIEW_LIMIT" class="name-more">… 其余 {{ names.length - PREVIEW_LIMIT }} 条未展示</div>
      </div>
      <div class="resolve-option">
        <el-checkbox v-model="resolveOnImport">导入后自动补全官网 / 招聘网址 / 行业</el-checkbox>
        <div class="option-hint">勾选后批量补全走异步任务，逐条展示进度；补全结果需人工确认。</div>
      </div>
    </div>

    <!-- 步骤三：批量补全进度 -->
    <div v-else-if="step === 'running'">
      <el-progress :percentage="percent" :indeterminate="!progress" :stroke-width="12" />
      <div class="running-text">
        {{ progressText || (progress ? `已补全 ${progress.done} / ${progress.total}` : '任务排队中…') }}
      </div>
      <p class="hint">批量补全期间请勿关闭页面；完成后会汇总每家公司补全结果。</p>
    </div>

    <!-- 步骤四：结果 -->
    <div v-else-if="step === 'result'">
      <!-- 同步导入结果 -->
      <template v-if="syncResult">
        <div class="summary-line">
          <span class="ok-count">新增 {{ syncResult.added }} 家</span>
          <span v-if="syncResult.skipped" class="skip-count">跳过 {{ syncResult.skipped }} 家（已存在）</span>
        </div>
        <el-collapse v-if="syncResult.skipped_names.length" class="skip-collapse">
          <el-collapse-item :title="`跳过名单（${syncResult.skipped_names.length}）`">
            <div v-for="(n, i) in syncResult.skipped_names" :key="i" class="skip-name">{{ n }}</div>
          </el-collapse-item>
        </el-collapse>
      </template>

      <!-- 异步批量补全结果 -->
      <template v-else-if="asyncResult">
        <div class="summary-line">
          <span class="ok-count">成功补全 {{ asyncResult.ok }} 家</span>
          <span v-if="asyncResult.skipped" class="skip-count">跳过 {{ asyncResult.skipped }} 家</span>
          <span v-if="asyncResult.failed.length" class="fail-count">失败 {{ asyncResult.failed.length }} 家</span>
        </div>
        <div v-if="asyncResult.ok" class="done-hint">已写入公司库（官网 / 招聘网址 / 行业），可在列表中「编辑」修正。</div>
        <div v-if="failedDetails.length" class="fail-list">
          <div v-for="(d, i) in failedDetails" :key="i" class="fail-item">
            <span class="fail-name">{{ d.name }}</span>
            <span class="fail-reason">{{ d.error || '补全失败' }}</span>
          </div>
        </div>
      </template>
    </div>

    <template #footer>
      <el-button v-if="step !== 'running'" :disabled="submitting" @click="close">取消</el-button>
      <el-button
        v-if="step === 'preview'"
        type="primary"
        :loading="submitting"
        :disabled="!names.length"
        @click="onConfirm"
      >
        确认导入（{{ names.length }}）
      </el-button>
      <el-button v-if="step === 'result'" type="primary" @click="close">完成</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint {
  font-size: 12px;
  color: #6b7280;
  margin: 0 0 12px;
}
.pick-box {
  padding: 24px 0;
  text-align: center;
}
.pick-action {
  margin-top: 8px;
}
.preview-summary {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
}
.file-name {
  font-size: 13px;
  color: #1f2937;
  font-weight: 600;
}
.preview-hint {
  font-size: 12px;
  color: #9ca3af;
}
.name-list {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  max-height: 240px;
  overflow-y: auto;
  padding: 4px 0;
}
.name-item {
  padding: 4px 12px;
  font-size: 13px;
  color: #374151;
  border-bottom: 1px solid #f3f4f6;
}
.name-item:last-child {
  border-bottom: none;
}
.name-more {
  padding: 6px 12px;
  font-size: 12px;
  color: #9ca3af;
}
.resolve-option {
  margin-top: 12px;
  font-size: 13px;
}
.option-hint {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 2px;
}
.running-text {
  margin-top: 12px;
  font-size: 13px;
  color: #374151;
  text-align: center;
}
.summary-line {
  display: flex;
  gap: 16px;
  font-size: 14px;
  margin-bottom: 12px;
}
.ok-count {
  color: #15803d;
  font-weight: 600;
}
.skip-count {
  color: #b45309;
}
.fail-count {
  color: #dc2626;
}
.skip-collapse {
  margin-bottom: 8px;
}
.skip-name {
  font-size: 13px;
  color: #6b7280;
  padding: 2px 0;
}
.done-hint {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 10px;
}
.fail-list {
  border: 1px solid #fecaca;
  background: #fef2f2;
  border-radius: 8px;
  max-height: 200px;
  overflow-y: auto;
  padding: 8px 12px;
}
.fail-item {
  display: flex;
  gap: 8px;
  align-items: baseline;
  padding: 3px 0;
}
.fail-name {
  font-size: 13px;
  color: #374151;
  min-width: 96px;
}
.fail-reason {
  font-size: 12px;
  color: #dc2626;
  word-break: break-all;
}
</style>
