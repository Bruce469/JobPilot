<script setup lang="ts">
import { computed } from 'vue'
import { statusMeta } from '@/utils/normalize'

const props = defineProps<{ status: string; size?: 'small' | 'default' }>()

const meta = computed(() => statusMeta(props.status))
</script>

<template>
  <span
    class="status-badge"
    :class="size === 'small' ? 'status-badge--small' : ''"
    :style="{ color: meta.color, background: meta.bg, borderColor: meta.border }"
  >
    {{ status }}
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border: 1px solid transparent;
  border-radius: 10px;
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
}
.status-badge--small {
  padding: 0 6px;
  font-size: 11px;
  line-height: 16px;
  border-radius: 9px;
}
</style>
