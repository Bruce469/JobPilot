<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useJobsStore } from '@/stores/jobs'
import { useUiStore } from '@/stores/ui'
import { useCompaniesStore } from '@/stores/companies'
import { useResumesStore } from '@/stores/resumes'
import { useStatusFlow } from '@/composables/useStatusFlow'
import { ACTIVE_STATUSES, STATUS_ALL, isTerminal } from '@/utils/normalize'
import { eventInRange, formatDate, formatDateTime, isWithinDays } from '@/utils/date'
import type { Job, JobEvent } from '@/types'
import KanbanColumn from '@/components/KanbanColumn.vue'
import type { DragEndPayload } from '@/components/KanbanColumn.vue'
import JobFormModal from '@/components/JobFormModal.vue'
import TimelinePanel from '@/components/TimelinePanel.vue'
import EmptyGuide from '@/components/EmptyGuide.vue'

const jobsStore = useJobsStore()
const uiStore = useUiStore()
const companiesStore = useCompaniesStore()
const resumesStore = useResumesStore()
const { flowStatus } = useStatusFlow()

const { items, loading, eventsByJob } = storeToRefs(jobsStore)
const includeEnded = computed({
  get: () => uiStore.includeEnded,
  set: (v: boolean) => {
    if (uiStore.includeEnded !== v) {
      uiStore.toggleIncludeEnded()
      void load()
    }
  },
})

const keyword = ref('')

// 看板展示的状态列：终态默认收起，开启「含已结束」后展示
const columnsToShow = computed(() => (includeEnded.value ? STATUS_ALL : ACTIVE_STATUSES))

const grouped = computed<Record<string, Job[]>>(() => {
  const g: Record<string, Job[]> = {}
  for (const s of STATUS_ALL) g[s] = []
  const kw = keyword.value.trim().toLowerCase()
  for (const j of items.value) {
    if (!columnsToShow.value.includes(j.status)) continue
    if (kw && !(j.company.toLowerCase().includes(kw) || (j.position ?? '').toLowerCase().includes(kw))) continue
    g[j.status].push(j)
  }
  return g
})

const hasAnyJob = computed(() => items.value.length > 0)

// ---------------- 顶部安排区 ----------------
interface ScheduleItem {
  job: Job
  ev: JobEvent
}

function scheduleItems(rangeDays: number): ScheduleItem[] {
  const out: ScheduleItem[] = []
  for (const job of items.value) {
    if (isTerminal(job.status)) continue
    const events = eventsByJob.value[job.id] ?? []
    for (const ev of events) {
      if (ev.type !== '状态流转') continue
      if (eventInRange(ev.time, rangeDays)) out.push({ job, ev })
    }
  }
  out.sort((a, b) => a.ev.time.localeCompare(b.ev.time))
  return out
}

const todaySchedule = computed(() => scheduleItems(0))
const weekSchedule = computed(() => scheduleItems(7))

const upcomingDeadlines = computed(() =>
  items.value
    .filter((j) => j.deadline && !isTerminal(j.status) && isWithinDays(j.deadline, 3))
    .sort((a, b) => (a.deadline! > b.deadline! ? 1 : -1)),
)

// ---------------- 加载 ----------------
async function load() {
  await jobsStore.fetchJobs({ include_ended: uiStore.includeEnded })
  await jobsStore.loadActiveEvents()
}

onMounted(() => {
  void load()
})

// ---------------- 拖拽流转 ----------------
async function onDragEnd(evt: DragEndPayload) {
  const toStatus = evt.to?.closest('.kanban-column')?.getAttribute('data-status') ?? null
  const fromStatus = evt.from?.closest('.kanban-column')?.getAttribute('data-status') ?? null
  const idEl = evt.item?.querySelector('[data-id]') ?? evt.item
  const id = idEl?.getAttribute('data-id')
  if (!toStatus || !id || toStatus === fromStatus) return
  try {
    await jobsStore.changeStatus(id, toStatus)
    ElMessage.success(`已流转至「${toStatus}」`)
    // 刷新该岗位事件，保证时间线/安排区及时更新
    await jobsStore.loadEvents([id])
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '状态流转失败')
    void load() // 回滚到后端实际状态
  }
}

async function onStatusChange(payload: { id: string; status: string }) {
  const ok = await flowStatus(payload.id, payload.status)
  if (ok) {
    await jobsStore.loadEvents([payload.id])
  }
}

// ---------------- 详情 / 编辑 / 删除 ----------------
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
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  }
}

async function onDelete(job: Job) {
  try {
    await ElMessageBox.confirm(`确认删除岗位「${job.company}${job.position ? ' - ' + job.position : ''}」？删除后不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
    })
    await jobsStore.deleteJob(job.id)
    ElMessage.success('已删除')
  } catch {
    // 取消
  }
}

// 首次引导用：公司/简历数据在挂载时顺带拉取，便于空态判断与表单下拉
onMounted(() => {
  void companiesStore.fetchCompanies().catch(() => undefined)
  void resumesStore.fetchResumes().catch(() => undefined)
})
</script>

<template>
  <div class="board-page">
    <!-- 工具栏 -->
    <div class="board-toolbar">
      <el-input v-model="keyword" placeholder="筛选公司 / 岗位关键词（当前视图内）" clearable class="toolbar-search" />
      <div class="toolbar-right">
        <el-switch v-model="includeEnded" active-text="含已结束" />
        <el-button :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" @click="openCreate">新增岗位</el-button>
      </div>
    </div>

    <!-- 首次使用引导 -->
    <EmptyGuide v-if="!loading && !hasAnyJob" />

    <template v-else>
      <!-- 顶部安排区 -->
      <div v-if="todaySchedule.length || weekSchedule.length || upcomingDeadlines.length" class="schedule-grid">
        <div class="schedule-card">
          <div class="schedule-title">今日安排</div>
          <div v-if="todaySchedule.length" class="schedule-list">
            <div v-for="item in todaySchedule" :key="item.ev.id" class="schedule-item">
              <span class="schedule-time">{{ formatDateTime(item.ev.time) }}</span>
              <span class="schedule-text">{{ item.job.company }}<template v-if="item.job.position"> · {{ item.job.position }}</template></span>
              <span class="schedule-status">→ {{ item.ev.to_status }}</span>
            </div>
          </div>
          <div v-else class="schedule-empty">今天暂无安排</div>
        </div>

        <div class="schedule-card">
          <div class="schedule-title">本周安排</div>
          <div v-if="weekSchedule.length" class="schedule-list">
            <div v-for="item in weekSchedule" :key="item.ev.id" class="schedule-item">
              <span class="schedule-time">{{ formatDateTime(item.ev.time) }}</span>
              <span class="schedule-text">{{ item.job.company }}<template v-if="item.job.position"> · {{ item.job.position }}</template></span>
              <span class="schedule-status">→ {{ item.ev.to_status }}</span>
            </div>
          </div>
          <div v-else class="schedule-empty">本周暂无安排</div>
        </div>

        <div class="schedule-card">
          <div class="schedule-title">即将截止（≤3 天）</div>
          <div v-if="upcomingDeadlines.length" class="schedule-list">
            <div v-for="job in upcomingDeadlines" :key="job.id" class="schedule-item">
              <span class="schedule-time">{{ formatDate(job.deadline) }}</span>
              <span class="schedule-text">{{ job.company }}<template v-if="job.position"> · {{ job.position }}</template></span>
              <span class="schedule-status deadline-tag">{{ job.status }}</span>
            </div>
          </div>
          <div v-else class="schedule-empty">无即将截止</div>
        </div>
      </div>

      <!-- 看板 -->
      <div class="kanban">
        <div class="kanban-scroll">
          <KanbanColumn
            v-for="status in columnsToShow"
            :key="status"
            :status="status"
            :jobs="grouped[status]"
            @end="onDragEnd"
            @status-change="onStatusChange"
            @detail="openDetail"
            @edit="openEdit"
            @delete="onDelete"
          />
        </div>
      </div>
    </template>

    <!-- 详情（时间线） -->
    <el-dialog v-model="detailVisible" :title="detailJob ? `${detailJob.company} · ${detailJob.position || '未填写岗位'}` : '岗位详情'" width="520px">
      <div v-loading="detailLoading">
        <div v-if="detailJob" class="detail-head">
          <span class="detail-status">{{ detailJob.status }}</span>
          <span v-if="detailJob.deadline" class="detail-deadline">截止 {{ formatDate(detailJob.deadline) }}</span>
          <span v-if="detailJob.city">{{ detailJob.city }}</span>
          <span v-if="detailJob.resume_name">简历：{{ detailJob.resume_name }}</span>
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
.board-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.board-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.toolbar-search {
  max-width: 320px;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.schedule-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.schedule-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px 12px;
}
.schedule-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 6px;
}
.schedule-list {
  max-height: 132px;
  overflow-y: auto;
}
.schedule-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12px;
  padding: 2px 0;
}
.schedule-time {
  color: #2563eb;
  white-space: nowrap;
}
.schedule-text {
  color: #1f2937;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.schedule-status {
  color: #6b7280;
  white-space: nowrap;
}
.schedule-status.deadline-tag {
  color: #b45309;
}
.schedule-empty {
  font-size: 12px;
  color: #9ca3af;
}
.kanban {
  flex: 1;
  overflow-x: auto;
  min-height: 200px;
}
.kanban-scroll {
  display: flex;
  gap: 12px;
  min-width: min-content;
  height: 100%;
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
.detail-status {
  font-weight: 600;
  color: #1f2937;
}
.detail-deadline {
  color: #b45309;
}
</style>
