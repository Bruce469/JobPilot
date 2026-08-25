<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useJobsStore } from '@/stores/jobs'
import { useCompaniesStore } from '@/stores/companies'
import { useResumesStore } from '@/stores/resumes'
import { useStatusFlow } from '@/composables/useStatusFlow'
import type { JobFilters } from '@/api/jobs'
import type { Job, JobEvent } from '@/types'
import { CHANNELS, INDUSTRIES, SORT_FIELDS, STATUS_ALL, overdueEventOf } from '@/utils/normalize'
import { deadlineLabel, formatDate, formatDateTime } from '@/utils/date'
import StatusBadge from '@/components/StatusBadge.vue'
import JobFormModal from '@/components/JobFormModal.vue'
import TimelinePanel from '@/components/TimelinePanel.vue'
import type { TableInstance } from 'element-plus'

const jobsStore = useJobsStore()
const companiesStore = useCompaniesStore()
const resumesStore = useResumesStore()
const { flowStatus } = useStatusFlow()

const { items, loading, eventsByJob } = storeToRefs(jobsStore)

const FILTERS_KEY = 'job_list_filters_v1'

interface FilterState {
  keyword: string
  company: string
  city: string
  industry: string | null
  channel: string | null
  status: string[]
  includeEnded: boolean
  sort: string
  sortDir: 'asc' | 'desc'
}

function defaultFilters(): FilterState {
  return {
    keyword: '',
    company: '',
    city: '',
    industry: null,
    channel: null,
    status: [],
    includeEnded: false,
    sort: 'updated_at',
    sortDir: 'desc',
  }
}

function loadSavedFilters(): FilterState {
  try {
    const raw = localStorage.getItem(FILTERS_KEY)
    if (!raw) return defaultFilters()
    return { ...defaultFilters(), ...(JSON.parse(raw) as Partial<FilterState>) }
  } catch {
    return defaultFilters()
  }
}

const filters = reactive<FilterState>(loadSavedFilters())

watch(filters, () => {
  localStorage.setItem(FILTERS_KEY, JSON.stringify(filters))
}, { deep: true })

const selection = ref<string[]>([])

function toApiFilters(): JobFilters {
  return {
    status: filters.status.length ? filters.status : null,
    company: filters.company || null,
    city: filters.city || null,
    industry: filters.industry || null,
    channel: filters.channel || null,
    keyword: filters.keyword || null,
    include_ended: filters.includeEnded,
    sort: filters.sort,
    sort_dir: filters.sortDir,
  }
}

let debounceTimer: number | undefined

function requestFetch() {
  if (debounceTimer !== undefined) window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => {
    void load()
  }, 250)
}

async function load() {
  try {
    await jobsStore.fetchJobs(toApiFilters())
    // 拉取非终态岗位事件，用于列表过期事件标红提醒
    await jobsStore.loadActiveEvents()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载岗位列表失败')
  }
}

onMounted(() => {
  void load()
  void companiesStore.fetchCompanies().catch(() => undefined)
  void resumesStore.fetchResumes().catch(() => undefined)
})

const filtersKey = computed(() => JSON.stringify(filters))
watch(filtersKey, requestFetch)

function clearFilters() {
  Object.assign(filters, defaultFilters())
}

// ---------------- 排序 ----------------
function onSortChange({ prop, order }: { prop: string | null; order: string | null }) {
  filters.sort = prop && prop !== '' ? prop : 'updated_at'
  filters.sortDir = order === 'ascending' ? 'asc' : 'desc'
}

// ---------------- 行内状态流转 ----------------
async function onRowStatusChange(row: Job, status: string) {
  if (status === row.status) return
  const ok = await flowStatus(row.id, status)
  if (ok) {
    await jobsStore.loadEvents([row.id])
  }
}

// ---------------- 过期事件标红 ----------------
const overdueByJob = computed<Record<string, JobEvent>>(() => {
  const m: Record<string, JobEvent> = {}
  for (const j of items.value) {
    const ev = overdueEventOf(j, eventsByJob.value[j.id] ?? [])
    if (ev) m[j.id] = ev
  }
  return m
})

function overdueTip(job: Job): string {
  const ev = overdueByJob.value[job.id]
  return ev ? `「${ev.to_status}」事件时间 ${formatDateTime(ev.time)} 已过，状态未推进，请跟进` : ''
}

// ---------------- 删除 / 批量删除 ----------------
async function onDelete(job: Job) {
  try {
    await ElMessageBox.confirm(`确认删除岗位「${job.company}${job.position ? ' - ' + job.position : ''}」？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
    })
    await jobsStore.deleteJob(job.id)
    ElMessage.success('已删除')
  } catch {
    // 取消
  }
}

async function onBatchDelete() {
  if (!selection.value.length) {
    ElMessage.warning('请先勾选要删除的岗位')
    return
  }
  try {
    await ElMessageBox.confirm(`确认删除选中的 ${selection.value.length} 条岗位？删除后不可恢复。`, '批量删除', {
      type: 'warning',
      confirmButtonText: '删除',
    })
    const res = await jobsStore.batchDelete(selection.value)
    selection.value = []
    ElMessage.success(`已删除 ${res.deleted} 条`)
  } catch {
    // 取消
  }
}

// ---------------- 详情 / 编辑 ----------------
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailJob = ref<Job | null>(null)
const detailEvents = ref<JobEvent[]>([])

async function openDetail(job: Job) {
  detailJob.value = job
  detailVisible.value = true
  detailLoading.value = true
  try {
    const detail = await jobsStore.loadDetail(job.id)
    detailJob.value = detail
    detailEvents.value = detail.events ?? []
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

const formVisible = ref(false)
const formJob = ref<Job | null>(null)

function openCreate() {
  formJob.value = null
  formVisible.value = true
}
function openEdit(job: Job) {
  formJob.value = job
  formVisible.value = true
}

async function onFormSubmit(payload: Parameters<typeof jobsStore.createJob>[0]) {
  try {
    if (formJob.value) {
      await jobsStore.updateJob(formJob.value.id, payload)
      ElMessage.success('岗位已更新')
    } else {
      await jobsStore.createJob(payload)
      ElMessage.success('岗位已创建')
    }
    formVisible.value = false
    void load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  }
}

const tableRef = ref<TableInstance>()

function onSelectionChange(rows: Job[]) {
  selection.value = rows.map((r) => r.id)
}

function deadlineCell(job: Job) {
  const l = deadlineLabel(job.deadline)
  return { label: l.text || '—', kind: l.kind }
}
</script>

<template>
  <div class="list-page">
    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input v-model="filters.keyword" placeholder="公司 / 岗位关键词" clearable class="filter-item keyword" @keyup.enter="requestFetch" />
      <el-input v-model="filters.company" placeholder="公司名（LIKE）" clearable class="filter-item" />
      <el-input v-model="filters.city" placeholder="城市" clearable class="filter-item" />
      <el-select v-model="filters.industry" placeholder="行业" clearable filterable allow-create default-first-option class="filter-item">
        <el-option v-for="i in INDUSTRIES" :key="i" :label="i" :value="i" />
      </el-select>
      <el-select v-model="filters.channel" placeholder="渠道" clearable class="filter-item">
        <el-option v-for="c in CHANNELS" :key="c" :label="c" :value="c" />
      </el-select>
      <el-select v-model="filters.status" placeholder="状态（多选）" multiple clearable collapse-tags class="filter-item status">
        <el-option v-for="s in STATUS_ALL" :key="s" :label="s" :value="s" />
      </el-select>
      <el-switch v-model="filters.includeEnded" active-text="含已结束" class="filter-item" />
      <el-button @click="clearFilters">清除筛选</el-button>
      <el-button :loading="loading" @click="load">搜索</el-button>
    </div>

    <!-- 表格 -->
    <el-table
      ref="tableRef"
      v-loading="loading"
      :data="items"
      row-key="id"
      :default-sort="{ prop: filters.sort, order: filters.sortDir === 'asc' ? 'ascending' : 'descending' }"
      @sort-change="onSortChange"
      @selection-change="onSelectionChange"
      class="job-table"
      size="default"
    >
      <el-table-column type="selection" width="44" />
      <el-table-column prop="company" label="公司" sortable="custom" min-width="150" show-overflow-tooltip />
      <el-table-column prop="position" label="岗位" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.position" class="position-cell">{{ row.position }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="132">
        <template #default="{ row }">
          <el-tooltip v-if="overdueTip(row as Job)" :content="overdueTip(row as Job)" placement="top">
            <div class="status-cell overdue-mark">
              <el-select
                :model-value="row.status"
                size="small"
                style="width: 108px"
                @change="(val: string) => onRowStatusChange(row as Job, val)"
              >
                <el-option v-for="s in STATUS_ALL" :key="s" :label="s" :value="s" />
              </el-select>
            </div>
          </el-tooltip>
          <div v-else class="status-cell">
            <el-select
              :model-value="row.status"
              size="small"
              style="width: 108px"
              @change="(val: string) => onRowStatusChange(row as Job, val)"
            >
              <el-option v-for="s in STATUS_ALL" :key="s" :label="s" :value="s" />
            </el-select>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="城市" min-width="90" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.city">{{ row.city }}</span><span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="行业" width="90" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.industry">{{ row.industry }}</span><span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="渠道" width="96" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.channel">{{ row.channel }}</span><span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="deadline" label="截止日期" sortable="custom" width="130">
        <template #default="{ row }">
          <span v-if="row.deadline" :class="['deadline', deadlineCell(row as Job).kind]">{{ formatDate(row.deadline) }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="applied_at" label="投递时间" sortable="custom" width="110">
        <template #default="{ row }">
          <span v-if="row.applied_at">{{ formatDate(row.applied_at) }}</span><span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="更新时间" sortable="custom" width="150">
        <template #default="{ row }">
          <span class="muted">{{ formatDateTime(row.updated_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="简历" width="110" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.resume_name">{{ row.resume_name }}</span><span v-else class="muted">未绑定</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row as Job)">详情</el-button>
          <el-button link type="primary" @click="openEdit(row as Job)">编辑</el-button>
          <el-button link type="danger" @click="onDelete(row as Job)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="table-empty">
          <el-empty description="没有符合条件的岗位">
            <el-button type="primary" @click="openCreate">新增岗位</el-button>
          </el-empty>
        </div>
      </template>
    </el-table>

    <!-- 底部操作条 -->
    <div class="list-footer">
      <span class="total-info">共 {{ jobsStore.total }} 条</span>
      <div class="footer-actions">
        <el-button type="danger" plain :disabled="!selection.length" @click="onBatchDelete">
          批量删除{{ selection.length ? `（${selection.length}）` : '' }}
        </el-button>
        <el-button type="primary" @click="openCreate">新增岗位</el-button>
      </div>
    </div>

    <!-- 详情 -->
    <el-dialog v-model="detailVisible" :title="detailJob ? `${detailJob.company} · ${detailJob.position || '未填写岗位'}` : '岗位详情'" width="520px">
      <div v-loading="detailLoading">
        <div v-if="detailJob" class="detail-head">
          <StatusBadge :status="detailJob.status" />
          <span v-if="detailJob.deadline" class="detail-deadline">截止 {{ formatDate(detailJob.deadline) }}</span>
          <span v-if="detailJob.city">{{ detailJob.city }}</span>
          <span v-if="detailJob.resume_name">简历：{{ detailJob.resume_name }}</span>
          <a v-if="detailJob.job_url" :href="detailJob.job_url" target="_blank" rel="noopener" class="detail-link">JD 链接</a>
        </div>
        <TimelinePanel :events="detailEvents" />
      </div>
    </el-dialog>

    <!-- 新增/编辑 -->
    <JobFormModal
      v-model="formVisible"
      :job="formJob"
      :companies="companiesStore.items"
      :resumes="resumesStore.items"
      @submit="onFormSubmit"
    />
  </div>
</template>

<style scoped>
.list-page {
  height: 100%;
  display: flex;
  flex-direction: column;
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
  width: 180px;
}
.filter-item.status {
  width: 180px;
}
.job-table {
  flex: 1;
  overflow-y: auto;
}
.list-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}
.total-info {
  font-size: 12px;
  color: #6b7280;
}
.footer-actions {
  display: flex;
  gap: 8px;
}
.position-cell {
  color: #1f2937;
}
.muted {
  color: #c0c4cc;
}
.deadline.overdue {
  color: #dc2626;
  font-weight: 600;
}
.deadline.urgent {
  color: #d97706;
  font-weight: 600;
}
.status-cell {
  display: inline-flex;
  align-items: center;
}
.overdue-mark {
  border-radius: 4px;
}
.overdue-mark :deep(.el-select) {
  box-shadow: 0 0 0 2px #fca5a5;
  border-radius: 4px;
}
.table-empty {
  padding: 24px 0;
}
.detail-head {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;
  color: #6b7280;
}
.detail-deadline {
  color: #b45309;
}
.detail-link {
  color: #2563eb;
  text-decoration: none;
}
</style>
