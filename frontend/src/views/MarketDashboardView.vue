<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getMarketSummary } from '@/api/market'
import type { MarketCharts, MarketFiltered, MarketSummary } from '@/types/market'
import type { EChartsCoreOption } from 'echarts/core'
import EChart from '@/components/EChart.vue'

const filters = reactive({ city: '', category: '', education: '', source: '' })
const summary = ref<MarketSummary | null>(null)
const filtered = ref<MarketFiltered | null>(null)
const chartsData = ref<MarketCharts | null>(null)
const sources = ref<string[]>([])
const loading = ref(false)
const error = ref('')

// 数据源下拉显示名（值仍为 source id，与 B 后端一致）
const SOURCE_LABELS: Record<string, string> = {
  backup: 'GitHub 数据集',
  job51: '51job',
  iguopin: '国聘网',
  nowcoder: '牛客网',
}
const sourceLabel = (s: string): string => SOURCE_LABELS[s] ?? s

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await getMarketSummary(filters)
    summary.value = data.summary
    filtered.value = data.filtered
    chartsData.value = data.charts
    sources.value = data.sources ?? []
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载市场情报失败'
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}
onMounted(load)

const cards = computed(() => {
  const f = filtered.value
  const s = summary.value
  return [
    { label: '当前筛选岗位数', value: f?.total ?? '-', desc: '按筛选条件' },
    { label: '平均月薪（元）', value: f && f.mean_salary ? f.mean_salary.toLocaleString() : '-', desc: '筛选后平均' },
    { label: '月薪中位数（元）', value: f && f.median_salary ? f.median_salary.toLocaleString() : '-', desc: '筛选后中位数' },
    { label: '覆盖城市', value: s?.cities?.length ?? '-', desc: '全量数据' },
  ]
})

const isEmpty = computed(() => !!filtered.value && filtered.value.total === 0)

// ① 薪资分布
const salaryHistOption = computed<EChartsCoreOption>(() => {
  const h = chartsData.value?.salary_hist
  if (!h) return {}
  const bins = h.bins.map((b, i) => `${Math.round(b / 1000)}-${Math.round((b + h.step) / 1000)}k`)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 44, right: 20, top: 28, bottom: 32 },
    xAxis: { type: 'category', data: bins, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: '岗位数' },
    series: [{ type: 'bar', data: h.counts, itemStyle: { color: '#4C72B0', borderRadius: [4, 4, 0, 0] } }],
  }
})

// ② 城市薪资对比（月薪中位数）
const citySalaryOption = computed<EChartsCoreOption>(() => {
  const d = chartsData.value?.city_salary
  if (!d) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: d.cities, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: '月薪中位数（元）' },
    series: [{ type: 'bar', data: d.medians, itemStyle: { color: '#55A868', borderRadius: [4, 4, 0, 0] } }],
  }
})

// ③ 技能需求 Top15（命中岗位占比）
const skillTopOption = computed<EChartsCoreOption>(() => {
  const top = chartsData.value?.skill_top
  if (!top) return {}
  const reversed = [...top].reverse()
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (p: { name: string; value: number }[]) => `${p[0].name}：${(p[0].value * 100).toFixed(1)}%`,
    },
    grid: { left: 100, right: 50, top: 10, bottom: 30 },
    xAxis: { type: 'value', name: '占比', axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` } },
    yAxis: { type: 'category', data: reversed.map((t) => t.name), axisLabel: { fontSize: 11 } },
    series: [{ type: 'bar', data: reversed.map((t) => t.ratio), itemStyle: { color: '#C44E52' } }],
  }
})

// ④ 岗位量占比（按类别）
const categoryDistOption = computed<EChartsCoreOption>(() => {
  const data = chartsData.value?.category_dist
  if (!data) return {}
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        name: '岗位类别',
        type: 'pie',
        radius: ['40%', '68%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b}\n{d}%' },
        data,
      },
    ],
  }
})

// ⑤ 城市 × 类别 岗位量热力图
const heatmapOption = computed<EChartsCoreOption>(() => {
  const hm = chartsData.value?.heatmap
  if (!hm) return {}
  return {
    tooltip: {
      position: 'top',
      formatter: (p: { value: number[] }) => `${hm.y[p.value[1]]}×${hm.x[p.value[0]]}：${p.value[2]} 条`,
    },
    grid: { left: 80, top: 20, right: 40, bottom: 60 },
    xAxis: { type: 'category', data: hm.x, splitArea: { show: true } },
    yAxis: { type: 'category', data: hm.y, splitArea: { show: true } },
    visualMap: { min: 0, max: Math.max(...hm.data.map((x) => x[2]), 1), calculable: true, orient: 'horizontal', left: 'center', bottom: 0 },
    series: [
      {
        type: 'heatmap',
        data: hm.data,
        label: { show: true, fontSize: 9 },
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.4)' } },
      },
    ],
  }
})
</script>

<template>
  <div v-loading="loading" class="market-page">
    <div class="market-toolbar">
      <h2 class="page-title">市场情报看板</h2>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <div class="filter-bar">
      <el-select v-model="filters.source" placeholder="数据源" clearable class="filter-item" @change="load">
        <el-option v-for="s in sources" :key="s" :label="sourceLabel(s)" :value="s" />
      </el-select>
      <el-select v-model="filters.city" placeholder="城市" clearable filterable class="filter-item" @change="load">
        <el-option v-for="c in summary?.cities ?? []" :key="c" :label="c" :value="c" />
      </el-select>
      <el-select v-model="filters.category" placeholder="岗位类别" clearable class="filter-item" @change="load">
        <el-option v-for="c in summary?.categories ?? []" :key="c" :label="c" :value="c" />
      </el-select>
      <el-select v-model="filters.education" placeholder="学历" clearable class="filter-item" @change="load">
        <el-option v-for="e in summary?.educations ?? []" :key="e" :label="e" :value="e" />
      </el-select>
    </div>

    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" class="market-error" />

    <el-empty v-if="!loading && !error && isEmpty" description="当前筛选条件下暂无岗位" />

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
          <div class="chart-title">薪资分布（筛选后）</div>
          <EChart :option="salaryHistOption" height="300px" />
        </div>
        <div class="chart-card">
          <div class="chart-title">城市薪资对比（月薪中位数）</div>
          <EChart :option="citySalaryOption" height="300px" />
        </div>
        <div class="chart-card">
          <div class="chart-title">技能需求 Top15（命中岗位占比）</div>
          <EChart :option="skillTopOption" height="300px" />
        </div>
        <div class="chart-card">
          <div class="chart-title">岗位量占比（按类别）</div>
          <EChart :option="categoryDistOption" height="300px" />
        </div>
        <div class="chart-card chart-full">
          <div class="chart-title">城市 × 岗位类别 岗位量热力图</div>
          <EChart :option="heatmapOption" height="360px" />
        </div>
      </div>
      <div v-if="summary?.generated_at" class="market-foot">数据生成时间 {{ summary.generated_at }}</div>
    </template>
  </div>
</template>

<style scoped>
.market-page {
  height: 100%;
  overflow-y: auto;
}
.market-toolbar {
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
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.filter-item {
  width: 160px;
}
.market-error {
  margin-bottom: 12px;
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
.market-foot {
  text-align: center;
  color: #9ca3af;
  font-size: 12px;
  padding: 14px 0 8px;
}
</style>
