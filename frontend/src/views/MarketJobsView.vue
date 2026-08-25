<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMarketJobs, getMarketMeta } from '@/api/market'
import { createJob, listJobs } from '@/api/jobs'
import { buildMarketJobPayload } from '@/utils/market'
import type { MarketJob, MarketJobsResponse, MarketMeta, MarketSortBy } from '@/types/market'

const router = useRouter()

const query = reactive({
  city: '',
  category: '',
  education: '',
  experience: '',
  job_type: '',
  keyword: '',
  source: '',
  page: 1,
  page_size: 10,
  sort_by: 'crawl_date' as MarketSortBy,
  order: 'desc' as 'asc' | 'desc',
})

const meta = ref<MarketMeta>({
  total: 0,
  mean_salary: 0,
  median_salary: 0,
  cities: [],
  categories: [],
  educations: [],
  generated_at: '',
  sources: [],
})
const result = ref<MarketJobsResponse>({ total: 0, page: 1, page_size: 10, total_pages: 0, items: [] })
const loading = ref(false)
const error = ref('')

const EXPERIENCES = ['不限', '1年以内', '1-3年', '3-5年', '5-10年', '10年以上']
const JOB_TYPES = ['不限', '社招', '校招', '实习']

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
    result.value = await getMarketJobs(query)
    if (!meta.value.cities.length) {
      meta.value = await getMarketMeta()
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载岗位列表失败'
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

function search() {
  query.page = 1
  void load()
}

function onPageChange(page: number) {
  query.page = page
  void load()
}

function onSizeChange(size: number) {
  query.page_size = size
  query.page = 1
  void load()
}

function onSortChange(val: MarketSortBy) {
  query.sort_by = val
  query.page = 1
  void load()
}

function toggleOrder() {
  query.order = query.order === 'desc' ? 'asc' : 'desc'
  void load()
}

onMounted(load)

function fmtSalary(j: MarketJob): string {
  if (j.salary_raw && j.salary_raw !== '面议') return j.salary_raw.replace(/[()]/g, '')
  return '面议'
}

// ---------------- 一键导入投递（P2b） ----------------
/** 公司名为空或 'nan'（pandas 脏值）时无法导入 */
function isBlankCompany(name: string): boolean {
  const s = name.trim()
  return s === '' || s.toLowerCase() === 'nan'
}

async function onImportJob(row: MarketJob) {
  const company = String(row.company ?? '').trim()
  if (isBlankCompany(company)) {
    ElMessage.warning('该公司名为空，无法导入')
    return
  }
  const position = row.title || '未填写岗位'
  try {
    await ElMessageBox.confirm(`确认将「${company} · ${position}」导入投递列表？`, '导入投递', {
      type: 'info',
      confirmButtonText: '确认导入',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }
  // 防重复：按公司名查 A 列表，命中相同 source_job_id 时二次确认（含已结束岗位）
  try {
    const res = await listJobs({ keyword: company, include_ended: true })
    const duplicated = res.items.some((j) => j.source_job_id === row.job_id)
    if (duplicated) {
      try {
        await ElMessageBox.confirm('该岗位已导入过投递列表，是否仍要导入？', '重复导入提示', {
          type: 'warning',
          confirmButtonText: '仍要导入',
          cancelButtonText: '取消',
        })
      } catch {
        return
      }
    }
  } catch {
    // 查重失败不阻塞导入
  }
  try {
    await createJob(buildMarketJobPayload(row))
    ElMessage({
      type: 'success',
      showClose: true,
      duration: 6000,
      message: h('span', {}, [
        '已导入投递列表 ',
        h(
          'a',
          {
            class: 'go-link',
            style: 'color:#2563eb;cursor:pointer;font-weight:600;margin-left:8px;',
            onClick: () => router.push('/jobs'),
          },
          '去查看',
        ),
      ]),
    })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '导入失败')
  }
}
</script>

<template>
  <div class="market-page">
    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-select v-model="query.source" placeholder="数据源" clearable class="filter-item" @change="search">
        <el-option v-for="s in meta.sources" :key="s" :label="sourceLabel(s)" :value="s" />
      </el-select>
      <el-select v-model="query.city" placeholder="城市" clearable filterable class="filter-item" @change="search">
        <el-option v-for="c in meta.cities" :key="c" :label="c" :value="c" />
      </el-select>
      <el-select v-model="query.category" placeholder="类别" clearable class="filter-item" @change="search">
        <el-option v-for="c in meta.categories" :key="c" :label="c" :value="c" />
      </el-select>
      <el-select v-model="query.education" placeholder="学历" clearable class="filter-item" @change="search">
        <el-option v-for="e in meta.educations" :key="e" :label="e" :value="e" />
      </el-select>
      <el-select v-model="query.experience" placeholder="经验" clearable class="filter-item" @change="search">
        <el-option v-for="e in EXPERIENCES" :key="e" :label="e" :value="e" />
      </el-select>
      <el-select v-model="query.job_type" placeholder="类型" clearable class="filter-item" @change="search">
        <el-option v-for="t in JOB_TYPES" :key="t" :label="t" :value="t" />
      </el-select>
      <el-input
        v-model="query.keyword"
        placeholder="搜索岗位 / 公司 / JD"
        clearable
        class="filter-item keyword"
        @keyup.enter="search"
        @clear="search"
      />
      <el-button :loading="loading" @click="search">搜索</el-button>
    </div>

    <!-- 结果统计与排序 -->
    <div class="meta-line">
      <span>共 {{ result.total.toLocaleString() }} 条</span>
      <el-select :model-value="query.sort_by" class="sort-select" @change="onSortChange">
        <el-option value="crawl_date" label="按采集时间" />
        <el-option value="post_date" label="按发布时间" />
        <el-option value="salary_avg" label="按薪资" />
      </el-select>
      <el-button size="small" @click="toggleOrder">{{ query.order === 'desc' ? '↓ 降序' : '↑ 升序' }}</el-button>
      <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" class="inline-error" />
    </div>

    <!-- 岗位表格 -->
    <el-table v-loading="loading" :data="result.items" row-key="job_id" class="job-table" size="default">
      <el-table-column label="岗位" min-width="220">
        <template #default="{ row }">
          <a v-if="row.url" :href="row.url" target="_blank" rel="noopener" class="job-title">{{ row.title }}</a>
          <span v-else class="job-title">{{ row.title }}</span>
          <div class="job-sub">
            {{ row.type }} · {{ row.industry }}{{ row.company_size ? ` · ${row.company_size}` : '' }}
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="company" label="公司" min-width="150" show-overflow-tooltip />
      <el-table-column prop="city" label="城市" width="90" />
      <el-table-column prop="category" label="类别" width="100" />
      <el-table-column label="薪资" width="150">
        <template #default="{ row }">
          <span class="salary">{{ fmtSalary(row as MarketJob) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="experience" label="经验" width="100" />
      <el-table-column prop="education" label="学历" width="90" />
      <el-table-column label="技能" min-width="180">
        <template #default="{ row }">
          <el-tag v-for="s in (row.skills || []).slice(0, 4)" :key="s" size="small" class="skill-tag">{{ s }}</el-tag>
          <el-tag v-if="row.skills_count > 4" size="small" type="info" class="skill-tag">+{{ row.skills_count - 4 }}</el-tag>
          <span v-if="!(row.skills || []).length" class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="发布时间" width="120">
        <template #default="{ row }">
          <span>{{ row.post_date || row.crawl_date || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="来源" width="100">
        <template #default="{ row }">
          <span>{{ sourceLabel(row.source) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="onImportJob(row as MarketJob)">导入投递</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="无匹配岗位" />
      </template>
    </el-table>

    <!-- 分页 -->
    <div class="pager">
      <el-pagination
        :current-page="query.page"
        :page-size="query.page_size"
        :page-sizes="[10, 20, 50]"
        :total="result.total"
        layout="total, sizes, prev, pager, next"
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>
  </div>
</template>

<style scoped>
.market-page {
  height: 100%;
  overflow-y: auto;
}
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.filter-item {
  width: 140px;
}
.filter-item.keyword {
  width: 200px;
}
.meta-line {
  display: flex;
  gap: 12px;
  align-items: center;
  margin: 12px 2px;
  font-size: 13px;
  color: #6b7280;
}
.sort-select {
  width: 140px;
}
.inline-error {
  flex: 1;
  padding: 4px 10px;
}
.job-table {
  width: 100%;
}
.job-title {
  color: #2563eb;
  font-weight: 600;
  text-decoration: none;
}
.job-sub {
  color: #9ca3af;
  font-size: 12px;
  margin-top: 2px;
}
.salary {
  color: #c44e52;
  font-weight: 600;
}
.skill-tag {
  margin: 1px 4px 1px 0;
}
.muted {
  color: #c0c4cc;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
