<script setup lang="ts">
import { computed } from 'vue'
import type { Job } from '@/types'
import { STATUS_ALL, arrangeOverdueOf } from '@/utils/normalize'
import { deadlineLabel, formatDateTime } from '@/utils/date'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{ job: Job }>()

const emit = defineEmits<{
  (e: 'status-change', payload: { id: string; status: string; fromStatus: string }): void
  (e: 'detail', job: Job): void
  (e: 'edit', job: Job): void
  (e: 'delete', job: Job): void
}>()

const deadline = computed(() => deadlineLabel(props.job.deadline))

// 等待环节安排时间（笔试/面试前缀语义 + 过期标红）
const arrange = computed(() => arrangeOverdueOf(props.job))
const arrangeText = computed(() => {
  if (!arrange.value) return ''
  const prefix = props.job.status === '笔试' ? '笔试' : '面试'
  return `${prefix}：${arrange.value.text}`
})
const arrangeOverdue = computed(() => arrange.value?.overdue ?? false)

// 最近一次流转备注（title 兜底展示完整内容）
const noteTitle = computed(() => {
  if (!props.job.last_note) return ''
  return props.job.last_note_at ? `${props.job.last_note}（${formatDateTime(props.job.last_note_at)}）` : props.job.last_note
})

function onCommand(cmd: string) {
  if (cmd === 'detail') emit('detail', props.job)
  else if (cmd === 'edit') emit('edit', props.job)
  else if (cmd === 'delete') emit('delete', props.job)
}
</script>

<template>
  <div class="job-card" :class="{ 'is-overdue': deadline.kind === 'overdue' }" :data-id="job.id">
    <div class="job-card-main" @click="emit('detail', job)">
      <div class="job-card-title">{{ job.company }}</div>
      <div class="job-card-position">{{ job.position || '（未填写岗位）' }}</div>
      <div v-if="deadline.text" class="job-card-deadline" :class="deadline.kind">
        <span class="dot"></span>{{ deadline.text }}
      </div>
    </div>
    <div class="job-card-meta">
      <span v-if="job.city" class="meta-item">{{ job.city }}</span>
      <span v-if="job.channel" class="meta-item">{{ job.channel }}</span>
      <span v-if="job.job_type" class="meta-item">{{ job.job_type }}</span>
      <span v-if="job.resume_name" class="meta-item resume">{{ job.resume_name }}</span>
    </div>
    <div class="job-card-actions" @click.stop>
      <div class="card-status-group">
        <el-dropdown trigger="click" @command="(cmd: string) => emit('status-change', { id: job.id, status: cmd, fromStatus: job.status })">
          <button class="card-btn status-btn" title="点击流转状态" @mousedown.stop>
            <StatusBadge :status="job.status" size="small" />
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="s in STATUS_ALL" :key="s" :command="s">
                <span class="status-option" :class="{ 'is-current': s === job.status }">
                  {{ s }}<span v-if="s === job.status" class="current-mark">当前</span>
                </span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-tag v-if="job.status === '已拒绝' && job.fail_stage" size="small" type="danger" effect="plain">
          {{ job.fail_stage }}
        </el-tag>
      </div>

      <el-dropdown trigger="click" @command="onCommand">
        <button class="card-btn more-btn" title="更多操作" @mousedown.stop>更多</button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="detail">查看时间线</el-dropdown-item>
            <el-dropdown-item command="edit">编辑</el-dropdown-item>
            <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <div v-if="arrangeText" class="job-card-arrange" :class="{ 'is-overdue': arrangeOverdue }">
      {{ arrangeText }}
    </div>
    <div v-if="job.last_note" class="job-card-note" :title="noteTitle">{{ job.last_note }}</div>
  </div>
</template>

<style scoped>
.job-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px 12px;
  cursor: grab;
  transition: box-shadow 0.15s, border-color 0.15s;
  margin-bottom: 8px;
  user-select: none;
}
.job-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  border-color: #c7d2fe;
}
.job-card:active {
  cursor: grabbing;
}
.job-card.is-overdue {
  border-left: 3px solid #dc2626;
}
.job-card-main {
  cursor: pointer;
}
.job-card-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.4;
}
.job-card-position {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.job-card-deadline {
  margin-top: 4px;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0 6px;
  border-radius: 4px;
  color: #6b7280;
  background: #f9fafb;
}
.job-card-deadline.urgent {
  color: #b45309;
  background: #fdf3e3;
}
.job-card-deadline.overdue {
  color: #b91c1c;
  background: #feecec;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.job-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}
.meta-item {
  font-size: 11px;
  color: #6b7280;
  background: #f3f4f6;
  padding: 0 5px;
  border-radius: 3px;
}
.meta-item.resume {
  color: #1d5bd7;
  background: #e8f0ff;
}
.job-card-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
.card-status-group {
  display: flex;
  align-items: center;
  gap: 4px;
}
.job-card-arrange {
  margin-top: 6px;
  font-size: 11px;
  color: #2563eb;
  background: #eef4ff;
  border-radius: 4px;
  padding: 1px 6px;
  display: inline-flex;
  align-items: center;
  line-height: 18px;
}
.job-card-arrange.is-overdue {
  color: #b91c1c;
  background: #feecec;
}
.job-card-note {
  margin-top: 4px;
  font-size: 11px;
  color: #6b7280;
  line-height: 16px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-btn {
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
}
.more-btn {
  font-size: 12px;
  color: #9ca3af;
}
.more-btn:hover {
  color: #4b5563;
}
.status-option.is-current {
  color: #2563eb;
}
.current-mark {
  margin-left: 4px;
  font-size: 11px;
  color: #2563eb;
}
</style>
