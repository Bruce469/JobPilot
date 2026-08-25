<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useJobsStore } from '@/stores/jobs'
import type { ImportResult } from '@/api/jobs'
import type { FetchTaskResult } from '@/types'

const props = defineProps<{
  modelValue: boolean
  companyId: string
  companyName: string
  result: FetchTaskResult | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'imported'): void
}>()

const jobsStore = useJobsStore()

const selected = ref<boolean[]>([])
const importing = ref(false)
const importResult = ref<ImportResult | null>(null)

const candidates = computed(() => props.result?.job_candidates ?? [])

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    importResult.value = null
    selected.value = candidates.value.map(() => true)
  },
)

const selectedCount = computed(() => selected.value.filter(Boolean).length)

function toggleAll(v: boolean | string | number) {
  const checked = v === true
  selected.value = candidates.value.map(() => checked)
}

async function doImport() {
  const jobs = candidates.value.filter((_, i) => selected.value[i])
  if (!jobs.length) {
    ElMessage.warning('请至少选择一条岗位')
    return
  }
  importing.value = true
  try {
    const res = await jobsStore.importJobs(props.companyId, jobs)
    importResult.value = res
    ElMessage.success(`导入完成：新增 ${res.added}，跳过 ${res.skipped}，失败 ${res.failed}`)
    emit('imported')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '导入失败')
  } finally {
    importing.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="抓取结果 - 岗位导入"
    width="760px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template v-if="!importResult">
      <div class="fetch-summary">
        <span>公司：<b>{{ companyName }}</b></span>
        <span v-if="result?.ats_type" class="ats-tag">ATS：{{ result.ats_type }}</span>
        <span>解析到 <b>{{ candidates.length }}</b> 条岗位</span>
      </div>

      <div v-if="candidates.length === 0" class="empty-hint">
        未解析到岗位。可能原因：招聘页为动态渲染或结构特殊。可在岗位列表中手动录入。
      </div>

      <div v-else class="preview-list">
        <div class="preview-head">
          <el-checkbox :model-value="selectedCount === candidates.length && candidates.length > 0" :indeterminate="selectedCount > 0 && selectedCount < candidates.length" @change="toggleAll">
            全选
          </el-checkbox>
          <span class="head-count">已选 {{ selectedCount }} / {{ candidates.length }}</span>
        </div>
        <div v-for="(c, i) in candidates" :key="i" class="preview-item">
          <el-checkbox v-model="selected[i]" />
          <div class="item-main">
            <div class="item-title">{{ c.position }}</div>
            <div class="item-sub">
              <span v-if="c.city">{{ c.city }}</span>
              <span v-if="c.job_type">{{ c.job_type }}</span>
              <span v-if="c.degree">{{ c.degree }}</span>
              <span v-if="c.deadline">截止 {{ c.deadline }}</span>
            </div>
          </div>
          <a v-if="c.job_url" :href="c.job_url" target="_blank" rel="noopener" class="item-link">打开</a>
        </div>
      </div>
    </template>

    <template v-else>
      <el-result
        icon="success"
        :title="`导入完成`"
        :sub-title="`新增 ${importResult.added} 条，跳过（去重）${importResult.skipped} 条，失败 ${importResult.failed} 条`"
      >
        <template #extra>
          <div v-if="importResult.failures.length" class="failures">
            <div v-for="(f, i) in importResult.failures" :key="i" class="failure-item">
              #{f.index}：{{ f.reason }}
            </div>
          </div>
          <el-button type="primary" @click="close">完成</el-button>
        </template>
      </el-result>
    </template>

    <template v-if="!importResult" #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="importing" :disabled="candidates.length === 0" @click="doImport">
        导入选中（{{ selectedCount }}）
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.fetch-summary {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 13px;
  color: #374151;
  margin-bottom: 12px;
}
.ats-tag {
  color: #2563eb;
  background: #e8f0ff;
  border-radius: 3px;
  padding: 0 6px;
}
.empty-hint {
  color: #9ca3af;
  font-size: 13px;
  background: #f9fafb;
  border-radius: 6px;
  padding: 16px;
}
.preview-list {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  max-height: 46vh;
  overflow-y: auto;
}
.preview-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  background: #fafafa;
}
.head-count {
  font-size: 12px;
  color: #6b7280;
}
.preview-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-bottom: 1px solid #f3f4f6;
}
.preview-item:last-child {
  border-bottom: none;
}
.item-main {
  flex: 1;
  min-width: 0;
}
.item-title {
  font-size: 13px;
  color: #1f2937;
}
.item-sub {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: #6b7280;
  margin-top: 2px;
}
.item-link {
  font-size: 12px;
  color: #2563eb;
  text-decoration: none;
}
.failures {
  text-align: left;
  font-size: 12px;
  color: #b91c1c;
  margin-bottom: 12px;
}
.failure-item {
  margin-bottom: 2px;
}
</style>
