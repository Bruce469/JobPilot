<script setup lang="ts">
import type { ProbeCandidate } from '@/types'

const props = defineProps<{
  modelValue: boolean
  companyName: string
  candidates: ProbeCandidate[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'select', url: string): void
}>()

function confidenceType(c: ProbeCandidate): 'success' | 'warning' | 'info' {
  if (c.confidence === 'high') return 'success'
  if (c.confidence === 'medium') return 'warning'
  return 'info'
}

function confidenceLabel(c: ProbeCandidate): string {
  return { high: '高置信', medium: '中置信', low: '低置信（需人工确认）' }[c.confidence] ?? c.confidence
}

function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="`探测结果 - ${companyName}`"
    width="640px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="hint">
      以下候选招聘入口按置信度排列，选择一个作为该公司的招聘页链接；也可先关闭后在编辑中手动填写 career_url。
    </p>
    <div v-if="candidates.length === 0" class="empty-hint">
      未发现明显的招聘入口。请手动填写招聘页链接，或直接在岗位列表录入岗位。
    </div>
    <div v-for="(c, i) in candidates" :key="i" class="candidate-item">
      <div class="cand-main">
        <div class="cand-url">{{ c.url }}</div>
        <div class="cand-reason">
          <el-tag :type="confidenceType(c)" size="small" effect="plain">{{ confidenceLabel(c) }}</el-tag>
          <span>{{ c.reason }}</span>
        </div>
      </div>
      <el-button size="small" type="primary" plain @click="emit('select', c.url)">使用此链接</el-button>
    </div>
    <template #footer>
      <el-button @click="close">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint {
  font-size: 12px;
  color: #6b7280;
  margin: 0 0 12px;
}
.empty-hint {
  color: #9ca3af;
  font-size: 13px;
  background: #f9fafb;
  border-radius: 6px;
  padding: 16px;
}
.candidate-item {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
}
.cand-main {
  flex: 1;
  min-width: 0;
}
.cand-url {
  font-size: 13px;
  color: #1d4ed8;
  word-break: break-all;
}
.cand-reason {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}
</style>
