<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getStats } from '@/api/stats'
import type { Stats } from '@/types'
import type { EChartsCoreOption } from 'echarts/core'
import EChart from '@/components/EChart.vue'

const stats = ref<Stats | null>(null)
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    stats.value = await getStats()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载统计失败')
  } finally {
    loading.value = false
  }
}
onMounted(load)

const isEmpty = computed(() => {
  const s = stats.value
  if (!s) return true
  return s.total_applied === 0 && s.active === 0 && s.offered === 0 && s.rejected === 0 && s.pending_followup === 0
})

const cards = computed(() => {
  const s = stats.value
  if (!s) return []
  return [
    { label: '总投递', value: s.total_applied, desc: '已投递及之后状态' },
    { label: '进行中', value: s.active, desc: '已投递 ~ 三面/HR面' },
    { label: '已 Offer', value: s.offered, desc: '终态' },
    { label: '已拒绝/放弃', value: s.rejected, desc: '终态' },
    { label: '待跟进', value: s.pending_followup, desc: '距上次流转 >3 天' },
  ]
})

const funnelOption = computed<EChartsCoreOption>(() => {
  const s = stats.value
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 条' },
    series: [
      {
        type: 'funnel',
        left: '10%',
        right: '10%',
        top: 16,
        bottom: 16,
        minSize: '20%',
        maxSize: '100%',
        sort: 'descending',
        gap: 2,
        label: { show: true, position: 'inside', color: '#fff', fontSize: 12 },
        itemStyle: { borderColor: '#fff', borderWidth: 1 },
        data: (s?.funnel ?? []).map((f) => ({ name: f.status, value: f.count })),
      },
    ],
  }
})

const channelOption = computed<EChartsCoreOption>(() => {
  const s = stats.value
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 条' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        name: '渠道',
        type: 'pie',
        radius: ['40%', '68%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b}: {c}' },
        data: (s?.channel_dist ?? []).map((c) => ({ name: c.channel, value: c.count })),
      },
    ],
  }
})

const trendOption = computed<EChartsCoreOption>(() => {
  const s = stats.value
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 44, right: 20, top: 28, bottom: 32 },
    xAxis: {
      type: 'category',
      data: (s?.weekly_trend ?? []).map((t) => t.week_start),
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '投递数',
        type: 'bar',
        barWidth: '42%',
        data: (s?.weekly_trend ?? []).map((t) => t.count),
        itemStyle: { color: '#2563eb', borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
})
</script>

<template>
  <div v-loading="loading" class="stats-page">
    <div class="stats-toolbar">
      <h2 class="page-title">统计面板</h2>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-empty v-if="!loading && isEmpty" description="暂无数据，先去录入或导入岗位吧">
      <router-link to="/jobs"><el-button type="primary">去岗位列表</el-button></router-link>
    </el-empty>

    <template v-else>
      <!-- 卡片数字 -->
      <div class="stat-cards">
        <div v-for="c in cards" :key="c.label" class="stat-card">
          <div class="stat-value">{{ c.value }}</div>
          <div class="stat-label">{{ c.label }}</div>
          <div class="stat-desc">{{ c.desc }}</div>
        </div>
      </div>

      <!-- 图表 -->
      <div class="chart-grid">
        <div class="chart-card">
          <div class="chart-title">投递漏斗（不含待投递）</div>
          <EChart :option="funnelOption" height="300px" />
        </div>
        <div class="chart-card">
          <div class="chart-title">渠道分布</div>
          <EChart :option="channelOption" height="300px" />
        </div>
        <div class="chart-card chart-full">
          <div class="chart-title">近 4 周投递趋势（按投递时间）</div>
          <EChart :option="trendOption" height="260px" />
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.stats-page {
  height: 100%;
  overflow-y: auto;
}
.stats-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}
.stat-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #2563eb;
}
.stat-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin-top: 4px;
}
.stat-desc {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 2px;
}
.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.chart-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
}
.chart-full {
  grid-column: 1 / -1;
}
.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}
</style>
