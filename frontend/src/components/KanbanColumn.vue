<script setup lang="ts">
import { ref } from 'vue'
import draggable from 'vuedraggable'
import type { Job } from '@/types'
import StatusBadge from './StatusBadge.vue'
import JobCard from './JobCard.vue'

export interface DragEndPayload {
  to: HTMLElement
  from: HTMLElement
  item: HTMLElement
  oldIndex?: number
  newIndex?: number
}

const props = defineProps<{ status: string; jobs: Job[] }>()

const emit = defineEmits<{
  (e: 'end', evt: DragEndPayload): void
  (e: 'status-change', payload: { id: string; status: string; fromStatus: string }): void
  (e: 'detail', job: Job): void
  (e: 'edit', job: Job): void
  (e: 'delete', job: Job): void
}>()

const dragOver = ref(false)
</script>

<template>
  <div
    class="kanban-column"
    :data-status="status"
    :class="{ 'is-drag-over': dragOver }"
    @dragover.prevent="dragOver = true"
    @dragleave="dragOver = false"
    @drop="dragOver = false"
  >
    <div class="kanban-column-header">
      <StatusBadge :status="status" />
      <span class="kanban-count">{{ jobs.length }}</span>
    </div>
    <draggable
      class="kanban-column-body"
      :class="{ 'is-empty': jobs.length === 0 }"
      :list="jobs"
      group="board"
      item-key="id"
      :animation="150"
      :empty-insert-threshold="40"
      @end="(evt: any) => emit('end', evt)"
    >
      <template #item="{ element }">
        <JobCard
          :job="element"
          @status-change="emit('status-change', $event)"
          @detail="emit('detail', $event)"
          @edit="emit('edit', $event)"
          @delete="emit('delete', $event)"
        />
      </template>
    </draggable>
  </div>
</template>

<style scoped>
.kanban-column {
  display: flex;
  flex-direction: column;
  background: #f5f6f8;
  border-radius: 10px;
  border: 1px solid transparent;
  min-height: 120px;
  max-height: 100%;
}
.kanban-column.is-drag-over {
  border-color: #2563eb;
  background: #eef4ff;
}
.kanban-column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
}
.kanban-count {
  font-size: 12px;
  color: #9ca3af;
  background: #fff;
  border-radius: 10px;
  padding: 0 8px;
  line-height: 18px;
}
.kanban-column-body {
  flex: 1;
  padding: 4px 8px 12px;
  overflow-y: auto;
  min-height: 60px;
}
.kanban-column-body.is-empty {
  border: 1px dashed #d1d5db;
  border-radius: 6px;
  margin: 0 8px 12px;
  padding: 4px;
  display: flex;
  align-items: flex-start;
}
</style>
