<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useCompaniesStore } from '@/stores/companies'
import type { BatchProbeResult, Company, CompanyResolveResult } from '@/types'

const props = defineProps<{
  modelValue: boolean
  mode: 'probe' | 'resolve'
  companies: Company[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'done'): void
}>()

const companiesStore = useCompaniesStore()

type Step = 'confirm' | 'running' | 'result'
const step = ref<Step>('confirm')
const submitting = ref(false)
const progress = ref<{ done: number; total: number } | null>(null)
const progressText = ref('')
const queueLength = ref(0)
const probeResult = ref<BatchProbeResult | null>(null)
const resolveResult = ref<{ ok: number; skipped: number; failed: CompanyResolveResult[] } | null>(null)

/** 实际需要处理的公司：补全只处理信息缺失的，探测只处理未探测成功的（其余自动跳过） */
const targetCompanies = computed(() =>
  isProbe.value
    ? props.companies.filter((c) => c.probe_status !== '成功')
    : props.companies.filter((c) => !c.website || !c.industry || !c.career_url),
)
const skipCount = computed(() => props.companies.length - targetCompanies.value.length)
const ids = computed(() => targetCompanies.value.map((c) => c.id))
const isProbe = computed(() => props.mode === 'probe')
const queued = computed(() => queueLength.value > 1)

watch(
  () => props.modelValue,
  (v) => {
    if (!v) return
    step.value = 'confirm'
    submitting.value = false
    progress.value = null
    progressText.value = ''
    queueLength.value = 0
    probeResult.value = null
    resolveResult.value = null
  },
)

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
  if (!ids.value.length) return
  submitting.value = true
  try {
    const jobId = isProbe.value
      ? await companiesStore.batchProbe(ids.value)
      : await companiesStore.batchResolve(ids.value)
    step.value = 'running'
    progress.value = null
    progressText.value = '排队中'
    const task = await companiesStore.pollTask(jobId, {
      interval: 1200,
      timeout: 30 * 60 * 1000,
      onProgress: (t) => {
        progress.value = parseProgress(t.progress)
        progressText.value = t.progress ?? ''
        queueLength.value = t.queue_length ?? 0
      },
    })
    if (isProbe.value) {
      const r = task.result as unknown as BatchProbeResult
      probeResult.value = r
      if (r.failed) ElMessage.warning(`探测完成：成功 ${r.ok} 家，需人工 ${r.manual} 家，失败 ${r.failed} 家${r.skipped ? `，跳过 ${r.skipped} 家` : ''}`)
      else ElMessage.success(`探测完成：成功 ${r.ok} 家${r.manual ? `，需人工 ${r.manual} 家` : ''}${r.skipped ? `，跳过 ${r.skipped} 家` : ''}`)
    } else {
      const details = (task.result as { results?: CompanyResolveResult[] })?.results ?? []
      const ok = details.filter((d) => d.source !== 'failed' && d.source !== 'skipped').length
      const skipped = details.filter((d) => d.source === 'skipped').length
      const failed = details.filter((d) => d.source === 'failed')
      resolveResult.value = { ok, skipped, failed }
      if (failed.length) ElMessage.warning(`补全完成：成功 ${ok} 家，失败 ${failed.length} 家${skipped ? `，跳过 ${skipped} 家` : ''}`)
      else ElMessage.success(`补全完成：成功 ${ok} 家${skipped ? `，跳过 ${skipped} 家` : ''}`)
    }
    step.value = 'result'
    emit('done')
  } catch (e) {
    if (step.value === 'running') step.value = 'confirm'
    ElMessage.error(e instanceof Error ? e.message : '批量操作失败')
  } finally {
    submitting.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="isProbe ? '批量探测' : '批量补全'"
    width="560px"
    :close-on-click-modal="false"
    :close-on-press-escape="!submitting"
    :show-close="!submitting"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <!-- 步骤一：确认 -->
    <div v-if="step === 'confirm'">
      <p class="hint" v-if="isProbe">
        将对选中的 <b>{{ companies.length }}</b> 家公司中未探测成功的 <b>{{ targetCompanies.length }}</b> 家逐家探测招聘入口：写入探测状态，缺失招聘页链接时自动填入探测到的最佳候选。预计每家企业约 10~60 秒，期间请勿关闭页面。
      </p>
      <p class="hint" v-else>
        将自动补全选中的 <b>{{ companies.length }}</b> 家公司中信息缺失的 <b>{{ targetCompanies.length }}</b> 家（官网 / 行业 / 招聘页链接，仅填充缺失字段，不覆盖已有数据）。每家公司约需 5~30 秒，期间请勿关闭页面。
      </p>
      <p v-if="skipCount" class="skip-hint">
        {{ skipCount }} 家{{ isProbe ? '已探测成功' : '信息已完整' }}，自动跳过。
      </p>
      <p v-if="!targetCompanies.length" class="skip-hint">
        所选公司均无需处理，可直接取消。
      </p>
      <div class="company-list">
        <div v-for="c in targetCompanies" :key="c.id" class="company-item">{{ c.name }}</div>
      </div>
    </div>

    <!-- 步骤二：进度 -->
    <div v-else-if="step === 'running'">
      <el-progress :percentage="percent" :indeterminate="!progress" :stroke-width="12" />
      <div class="running-text">
        <template v-if="queued">
          排队中：前面还有 {{ queueLength - 1 }} 个任务正在处理，完成后自动开始…
        </template>
        <template v-else>
          {{ progressText || (progress ? `${isProbe ? '已探测' : '已补全'} ${progress.done} / ${progress.total}` : '任务排队中…') }}
        </template>
      </div>
      <p v-if="progress && !queued" class="hint">
        {{ isProbe ? '正在探测第' : '正在补全第' }} {{ progress.done + 1 }} 家（共 {{ progress.total }} 家），每家约需 5~60 秒，请耐心等待。
      </p>
      <p v-else-if="queued" class="hint">批量任务串行执行，前面任务完成后本任务自动开始。</p>
    </div>

    <!-- 步骤三：结果 -->
    <div v-else-if="step === 'result'">
      <template v-if="isProbe && probeResult">
        <div class="summary-line">
          <span class="ok-count">成功 {{ probeResult.ok }} 家</span>
          <span v-if="probeResult.manual" class="skip-count">需人工 {{ probeResult.manual }} 家</span>
          <span v-if="probeResult.skipped" class="skip-count">跳过 {{ probeResult.skipped }} 家</span>
          <span v-if="probeResult.failed" class="fail-count">失败 {{ probeResult.failed }} 家</span>
        </div>
        <div class="done-hint">探测结果已写入公司库（探测状态 / 招聘页链接），可在列表中「编辑」修正。</div>
        <div v-if="probeResult.failed" class="fail-list">
          <div v-for="(d, i) in probeResult.results.filter((x) => x.status === 'failed')" :key="i" class="fail-item">
            <span class="fail-name">{{ d.name }}</span>
            <span class="fail-reason">{{ d.error || '探测失败' }}</span>
          </div>
        </div>
      </template>
      <template v-else-if="!isProbe && resolveResult">
        <div class="summary-line">
          <span class="ok-count">成功补全 {{ resolveResult.ok }} 家</span>
          <span v-if="resolveResult.skipped" class="skip-count">跳过 {{ resolveResult.skipped }} 家</span>
          <span v-if="resolveResult.failed.length" class="fail-count">失败 {{ resolveResult.failed.length }} 家</span>
        </div>
        <div v-if="resolveResult.ok" class="done-hint">已自动写入缺失字段（官网 / 行业 / 招聘页链接），未覆盖已有数据，可在列表中「编辑」修正。</div>
        <div v-if="resolveResult.failed.length" class="fail-list">
          <div v-for="(d, i) in resolveResult.failed" :key="i" class="fail-item">
            <span class="fail-name">{{ d.name }}</span>
            <span class="fail-reason">{{ d.error || '补全失败' }}</span>
          </div>
        </div>
      </template>
    </div>

    <template #footer>
      <el-button v-if="step !== 'running'" :disabled="submitting" @click="close">取消</el-button>
      <el-button
        v-if="step === 'confirm'"
        type="primary"
        :loading="submitting"
        :disabled="!targetCompanies.length"
        @click="onConfirm"
      >
        {{ isProbe ? '开始探测' : '开始补全' }}
      </el-button>
      <el-button v-if="step === 'result'" type="primary" @click="close">完成</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint {
  font-size: 13px;
  color: #6b7280;
  margin: 0 0 12px;
  line-height: 1.6;
}
.skip-hint {
  font-size: 12px;
  color: #b45309;
  margin: 0 0 12px;
}
.company-list {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  max-height: 240px;
  overflow-y: auto;
  padding: 4px 0;
}
.company-item {
  padding: 4px 12px;
  font-size: 13px;
  color: #374151;
  border-bottom: 1px solid #f3f4f6;
}
.company-item:last-child {
  border-bottom: none;
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
