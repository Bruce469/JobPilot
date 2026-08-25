<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { echarts } from '@/utils/charts'
import type { EChartsCoreOption } from 'echarts/core'

const props = defineProps<{ option: EChartsCoreOption; height?: string }>()

const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function render() {
  if (chart && props.option) chart.setOption(props.option, true)
}

function onResize() {
  chart?.resize()
}

onMounted(() => {
  if (el.value) {
    chart = echarts.init(el.value)
    render()
    window.addEventListener('resize', onResize)
  }
})

watch(() => props.option, render, { deep: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="el" class="echart" :style="{ height: height || '300px' }"></div>
</template>

<style scoped>
.echart {
  width: 100%;
}
</style>
