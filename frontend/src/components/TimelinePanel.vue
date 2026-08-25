<script setup lang="ts">
import { computed } from 'vue'
import type { JobEvent } from '@/types'
import { formatDateTime } from '@/utils/date'

const props = defineProps<{ events: JobEvent[] }>()

const sorted = computed(() => [...props.events].sort((a, b) => a.time.localeCompare(b.time)))

function timelineType(ev: JobEvent): 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  if (ev.type === '状态流转') {
    if (ev.to_status === '已Offer') return 'success'
    if (ev.to_status === '已拒绝' || ev.to_status === '已放弃') return 'danger'
    if (ev.to_status === '笔试') return 'warning'
    return 'primary'
  }
  return 'info'
}
</script>

<template>
  <div v-if="sorted.length" class="timeline-panel">
    <el-timeline>
      <el-timeline-item
        v-for="ev in sorted"
        :key="ev.id"
        :type="timelineType(ev)"
        :timestamp="formatDateTime(ev.time)"
        placement="top"
      >
        <div class="ev-content">
          <div v-if="ev.type === '状态流转'" class="ev-status">
            <template v-if="ev.from_status">{{ ev.from_status }} → </template>
            <b>{{ ev.to_status }}</b>
            <span class="ev-type-tag">状态流转</span>
          </div>
          <div v-else class="ev-type-line">
            <span class="ev-type-tag">{{ ev.type }}</span>
          </div>
          <div v-if="ev.note" class="ev-note">{{ ev.note }}</div>
        </div>
      </el-timeline-item>
    </el-timeline>
  </div>
  <el-empty v-else description="暂无时间线记录" :image-size="72" />
</template>

<style scoped>
.timeline-panel {
  max-height: 46vh;
  overflow-y: auto;
  padding-right: 8px;
}
.ev-status {
  font-size: 13px;
  color: #374151;
}
.ev-type-tag {
  margin-left: 8px;
  font-size: 11px;
  color: #9ca3af;
  background: #f3f4f6;
  border-radius: 3px;
  padding: 0 5px;
}
.ev-note {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
  white-space: pre-wrap;
  background: #f9fafb;
  border-radius: 4px;
  padding: 4px 8px;
}
.ev-type-line {
  font-size: 13px;
  color: #374151;
}
.ev-type-line .ev-type-tag {
  margin-left: 0;
}
</style>
