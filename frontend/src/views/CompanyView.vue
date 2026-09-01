<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import { storeToRefs } from 'pinia'
import { useCompaniesStore } from '@/stores/companies'
import { useJobsStore } from '@/stores/jobs'
import type { Company, Job, CompanyResolveResult } from '@/types'
import type { JobPayload } from '@/api/jobs'
import { COMPANY_NATURES, INDUSTRIES } from '@/utils/normalize'
import { COMMON_CITIES } from '@/utils/city'
import { RECENT_CITY_KEY, RECENT_NATURE_KEY, filterRecent, pushRecent, readRecent } from '@/utils/recent'
import { mergeCandidates, withRecentOnTop } from '@/utils/options'
import { listCompanyJobs } from '@/api/companies'
import MultiSelectFilterPopover from '@/components/MultiSelectFilterPopover.vue'
import CompanyImportModal from '@/components/CompanyImportModal.vue'
import CompanyBatchDialog from '@/components/CompanyBatchDialog.vue'
import CompanyJobFormModal from '@/components/CompanyJobFormModal.vue'
import ResolveResultDialog from '@/components/ResolveResultDialog.vue'
import StatusBadge from '@/components/StatusBadge.vue'

const companiesStore = useCompaniesStore()
const jobsStore = useJobsStore()
const { items, loading } = storeToRefs(companiesStore)

// ---------------- 导入 txt ----------------
const importVisible = ref(false)

// ---------------- 批量操作 ----------------
const selection = ref<string[]>([])
const batchVisible = ref(false)

function onSelectionChange(rows: Company[]) {
  selection.value = rows.map((r) => r.id)
}

function openBatch() {
  batchVisible.value = true
}

async function onBatchDelete() {
  if (!selection.value.length) return
  try {
    await ElMessageBox.confirm(
      `确认删除选中的 ${selection.value.length} 家公司？其岗位保留但解除关联。`,
      '批量删除',
      { type: 'warning', confirmButtonText: '删除' },
    )
    const res = await companiesStore.batchDelete(selection.value)
    selection.value = []
    ElMessage.success(`已删除 ${res.deleted} 家`)
    void load()
  } catch {
    // 取消
  }
}

function onBatchDone() {
  selection.value = []
  void load()
}

// ---------------- 展开岗位列表 / 添加岗位 ----------------
// 公司 id -> 已加载的岗位列表（懒加载：展开时拉取一次，后续增删本地维护）
const jobsByCompany = reactive<Record<string, Job[]>>({})
const jobsLoading = reactive<Record<string, boolean>>({})

async function loadCompanyJobs(c: Company) {
  if (jobsByCompany[c.id] || jobsLoading[c.id]) return
  jobsLoading[c.id] = true
  try {
    const data = await listCompanyJobs(c.id)
    jobsByCompany[c.id] = data.items
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载岗位失败')
  } finally {
    delete jobsLoading[c.id]
  }
}

/** element-plus 旧版本派发 (row, expandedRows[])，新版本派发 (row, expanded: boolean)，两者兼容处理 */
function onExpandChange(row: Company, expanded: boolean | Company[]) {
  const isExpanded = expanded === true || (Array.isArray(expanded) && expanded.some((r) => r.id === row.id))
  if (isExpanded) void loadCompanyJobs(row)
}

const jobFormVisible = ref(false)
const jobFormCompany = ref<Company | null>(null)

function openAddJob(c: Company) {
  jobFormCompany.value = c
  jobFormVisible.value = true
}

/** 添加岗位成功后：写入展开列表缓存、公司行岗位数 +1 */
async function onJobFormSubmit(payload: JobPayload) {
  const c = jobFormCompany.value
  if (!c) return
  try {
    const job = await jobsStore.createJob(payload)
    jobsByCompany[c.id] = [job, ...(jobsByCompany[c.id] ?? [])]
    const row = items.value.find((x) => x.id === c.id)
    if (row) row.job_count = (row.job_count ?? 0) + 1
    ElMessage.success('岗位已添加')
    jobFormVisible.value = false
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '添加岗位失败')
  }
}

async function onDeleteJob(c: Company, job: Job) {
  try {
    await ElMessageBox.confirm(`确认删除岗位「${job.position || '未命名岗位'}」？`, '删除岗位', {
      type: 'warning',
      confirmButtonText: '删除',
    })
    await jobsStore.deleteJob(job.id)
    jobsByCompany[c.id] = (jobsByCompany[c.id] ?? []).filter((j) => j.id !== job.id)
    const row = items.value.find((x) => x.id === c.id)
    if (row) row.job_count = Math.max(0, (row.job_count ?? 0) - 1)
  } catch {
    // 取消
  }
}

// ---------------- 筛选 ----------------
interface CompanyFilterState {
  keyword: string
  city: string[]
  industry: string[]
  nature: string | null
  processed: number | null
}

const filters = reactive<CompanyFilterState>({ keyword: '', city: [], industry: [], nature: null, processed: null })

// 城市候选池 = 内置常用城市 ∪ DB distinct 城市（去重）；弹窗内按拼音首字母分组
const cityOptions = computed(() => mergeCandidates(COMMON_CITIES, companiesStore.facets.cities))
// 行业候选池 = 静态 INDUSTRIES ∪ DB distinct 行业（去重，DB 独有行业必须保留）；弹窗内平铺
const industryOptions = computed(() => mergeCandidates(INDUSTRIES, companiesStore.facets.industries))
// 性质候选池 = 静态 COMPANY_NATURES ∪ DB distinct 性质（去重）；下拉选项再按最近点击置顶
const naturePool = computed(() => mergeCandidates(COMPANY_NATURES, companiesStore.facets.natures))

// readRecent 读 localStorage 无响应式依赖，写入后需版本号 +1 触发重算（城市/性质共用套路）
const recentCityVersion = ref(0)
const recentNatureVersion = ref(0)

// 最近选择：读取 localStorage 后按当前候选池过滤失效值；版本号变化时重读
const recentCities = computed(() => {
  void recentCityVersion.value
  return filterRecent(readRecent(RECENT_CITY_KEY), cityOptions.value)
})

/** 弹窗确定：批量写入最近选择（最新的在前），filters 由 v-model 更新并自动触发防抖 load */
function onCityConfirm(cities: string[]) {
  for (const c of cities) pushRecent(RECENT_CITY_KEY, c, 5)
  recentCityVersion.value += 1
}

// 性质下拉选项 = 最近点击置顶 + 完整候选池（去重、失效值过滤）
const natureOptions = computed(() => {
  void recentNatureVersion.value
  return withRecentOnTop(readRecent(RECENT_NATURE_KEY), naturePool.value)
})

/** 性质选中时写入最近点击（仅非空值；清空不记录），版本号 +1 保证下次打开下拉即新顺序 */
function onNatureChange(v: string | null) {
  if (v) {
    pushRecent(RECENT_NATURE_KEY, v, 10)
    recentNatureVersion.value += 1
  }
}

let debounceTimer: number | undefined

function requestFetch() {
  if (debounceTimer !== undefined) window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => {
    void load()
  }, 250)
}

const filtersKey = computed(() => JSON.stringify(filters))
watch(filtersKey, requestFetch)

function clearFilters() {
  Object.assign(filters, { keyword: '', city: [], industry: [], nature: null, processed: null })
  void load()
}

// ---------------- 列表加载 ----------------
async function load() {
  try {
    await companiesStore.fetchCompanies({
      city: filters.city.length ? filters.city : null,
      industry: filters.industry.length ? filters.industry : null,
      nature: filters.nature || null,
      processed: filters.processed,
      keyword: filters.keyword || null,
    })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载公司库失败')
  }
}
onMounted(() => {
  // 拉候选池（会话内只拉一次，失败不阻塞列表加载，城市弹窗仍可用内置常用城市）
  void companiesStore.fetchFacets().catch(() => {})
  void load()
})

// ---------------- 新增 / 编辑 ----------------
interface CompanyForm {
  name: string
  website: string
  industry: string | null
  city: string
  nature: string | null
  career_url: string
  notes: string
  processed: boolean
}

const formVisible = ref(false)
const editingId = ref<string | null>(null)
const form = reactive<CompanyForm>({
  name: '',
  website: '',
  industry: null,
  city: '',
  nature: null,
  career_url: '',
  notes: '',
  processed: false,
})

// 名称自动补全
const resolving = ref(false)
const resolveTip = ref('')
const resolveTipType = ref<'success' | 'warning' | 'info'>('info')

function openCreate() {
  editingId.value = null
  Object.assign(form, { name: '', website: '', industry: null, city: '', nature: null, career_url: '', notes: '', processed: false })
  resolveTip.value = ''
  formVisible.value = true
}

function openEdit(c: Company) {
  editingId.value = c.id
  Object.assign(form, {
    name: c.name,
    website: c.website,
    industry: c.industry,
    city: c.city || '',
    nature: c.nature,
    career_url: c.career_url || '',
    notes: c.notes || '',
    processed: !!c.processed,
  })
  resolveTip.value = ''
  formVisible.value = true
}

/** 仅输入公司名称自动获取官网/招聘网址/行业（POST /api/companies/resolve，不落库，结果可编辑） */
async function onAutoResolve() {
  const name = form.name.trim()
  if (!name) {
    ElMessage.warning('请先输入公司名称')
    return
  }
  resolving.value = true
  resolveTip.value = ''
  try {
    const res = await companiesStore.resolveName(name)
    if (res.source === 'failed') {
      ElMessage.error(res.error || '自动补全失败，可继续手填保存')
      return
    }
    if (res.website) form.website = res.website
    if (res.industry) form.industry = res.industry
    if (res.city) form.city = res.city
    if (res.nature) form.nature = res.nature
    if (res.career_url) form.career_url = res.career_url
    if (res.source === 'search') {
      resolveTip.value = '结果来自网络搜索，请核对后再保存'
      resolveTipType.value = 'warning'
      ElMessage.warning('结果来自网络搜索，请核对')
    } else {
      resolveTip.value = '已命中内置映射表，可编辑后保存'
      resolveTipType.value = 'success'
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '自动补全失败')
  } finally {
    resolving.value = false
  }
}

async function onFormSubmit() {
  if (!form.name.trim() || !form.website.trim()) {
    ElMessage.warning('公司名称与官网地址必填')
    return
  }
  try {
    if (editingId.value) {
      await companiesStore.updateCompany(editingId.value, {
        name: form.name.trim(),
        website: form.website.trim(),
        industry: form.industry,
        city: form.city.trim() || null,
        nature: form.nature,
        career_url: form.career_url.trim() || null,
        notes: form.notes.trim() || null,
        processed: form.processed ? 1 : 0,
      })
      ElMessage.success('公司已更新')
    } else {
      await companiesStore.createCompany({
        name: form.name.trim(),
        website: form.website.trim(),
        industry: form.industry,
        city: form.city.trim() || null,
        nature: form.nature,
        notes: form.notes.trim() || null,
      })
      ElMessage.success('公司已添加')
    }
    formVisible.value = false
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  }
}

async function onDelete(c: Company) {
  try {
    await ElMessageBox.confirm(`确认删除公司「${c.name}」？其岗位保留但解除关联。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
    })
    await companiesStore.deleteCompany(c.id)
    ElMessage.success('已删除')
  } catch {
    // 取消
  }
}

/** 行内切换「已处理/未处理」标签；若当前正按处理状态筛选，切换后重新拉取以保持列表一致 */
async function toggleProcessed(c: Company) {
  try {
    const next = c.processed ? 0 : 1
    await companiesStore.updateCompany(c.id, { processed: next })
    if (filters.processed != null) void load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '更新处理状态失败')
  }
}

function onImported() {
  void load()
}

// ---------------- 行级自动补全 ----------------
const resolveVisible = ref(false)
const resolveTarget = ref<Company | null>(null)
const resolveResult = ref<CompanyResolveResult | null>(null)
const resolvingRow = ref<string | null>(null)

/** website / industry / career_url 任一缺失时展示「补全」按钮 */
function needResolve(c: Company): boolean {
  return !c.website || !c.industry || !c.career_url
}

/** 对已存公司补全（POST /api/companies/{id}/resolve，不落库，弹窗内确认后保存） */
async function openResolve(c: Company) {
  resolvingRow.value = c.id
  try {
    const res = await companiesStore.resolveCompany(c.id)
    resolveTarget.value = c
    resolveResult.value = res
    resolveVisible.value = true
    if (res.source === 'failed') {
      ElMessage.warning(res.error || '补全失败')
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '补全失败')
  } finally {
    resolvingRow.value = null
  }
}
</script>

<template>
  <div class="company-page">
    <div class="company-toolbar">
      <el-button :loading="loading" @click="load">刷新</el-button>
      <div class="toolbar-right">
        <el-tooltip placement="top" effect="light" popper-class="import-help-popper">
          <template #content>
            <div class="import-help">
              <p class="help-title">功能介绍</p>
              <p>通过 txt 文件一键批量添加公司：自动忽略空行、按公司名去重，已存在的公司自动跳过。</p>
              <p class="help-title">txt 格式要求</p>
              <p>
                文件内容每行一个公司，按【公司全称】【城市】【行业】【公司性质（如国企）】【公司官网】顺序排列，
                各属性之间用空格隔开，一个公司占一行。例如：
              </p>
              <p class="help-example">字节跳动 北京 互联网 民营企业 https://www.bytedance.com</p>
              <p>
                若某项缺失，如在公司官网的位置为空、或写着「官网未公开」等明显不属于当前属性的内容，
                导入时该项将设为空；仅含公司名称的 txt 文件同样兼容。
              </p>
            </div>
          </template>
          <el-icon class="import-help-icon"><QuestionFilled /></el-icon>
        </el-tooltip>
        <el-button @click="importVisible = true">导入 txt</el-button>
        <el-button type="primary" @click="openCreate">添加公司</el-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input v-model="filters.keyword" placeholder="公司名关键词" clearable class="filter-item keyword" @keyup.enter="requestFetch" />
      <MultiSelectFilterPopover
        v-model="filters.city"
        :options="cityOptions"
        :recent="recentCities"
        title="城市"
        placeholder="城市"
        class="filter-item"
        @confirm="onCityConfirm"
      />
      <MultiSelectFilterPopover
        v-model="filters.industry"
        :options="industryOptions"
        :recent="[]"
        :grouped="false"
        title="行业"
        placeholder="行业"
        class="filter-item"
      />
      <el-select
        v-model="filters.nature"
        placeholder="公司性质"
        clearable
        filterable
        class="filter-item"
        @change="onNatureChange"
      >
        <el-option v-for="n in natureOptions" :key="n" :label="n" :value="n" />
      </el-select>
      <el-select v-model="filters.processed" placeholder="处理状态" clearable class="filter-item">
        <el-option label="未处理" :value="0" />
        <el-option label="已处理" :value="1" />
      </el-select>
      <el-button @click="clearFilters">清除筛选</el-button>
      <el-button :loading="loading" @click="load">搜索</el-button>
    </div>

    <el-table v-loading="loading" :data="items" row-key="id" class="company-table" @selection-change="onSelectionChange" @expand-change="onExpandChange">
      <el-table-column type="selection" width="44" />
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="company-jobs-panel">
            <div class="jobs-panel-head">
              <span class="jobs-panel-title">
                岗位列表
                <span class="jobs-panel-count">{{ jobsByCompany[row.id]?.length ?? row.job_count ?? 0 }} 个</span>
              </span>
              <el-button size="small" type="primary" plain @click="openAddJob(row as Company)">添加岗位</el-button>
            </div>
            <el-table v-if="jobsByCompany[row.id]?.length" :data="jobsByCompany[row.id]" size="small" class="jobs-table">
              <el-table-column label="岗位名称" min-width="160" show-overflow-tooltip>
                <template #default="{ row: job }">
                  <a v-if="job.job_url" :href="job.job_url" target="_blank" rel="noopener" class="link">{{ job.position || '未命名岗位' }}</a>
                  <span v-else>{{ job.position || '未命名岗位' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="城市" width="110" show-overflow-tooltip>
                <template #default="{ row: job }">
                  <span v-if="job.city">{{ job.city }}</span><span v-else class="muted">—</span>
                </template>
              </el-table-column>
              <el-table-column label="类型" width="90">
                <template #default="{ row: job }">
                  <span v-if="job.job_type">{{ job.job_type }}</span><span v-else class="muted">—</span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row: job }">
                  <StatusBadge :status="job.status" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="投递截止" width="110">
                <template #default="{ row: job }">
                  <span v-if="job.deadline">{{ job.deadline }}</span><span v-else class="muted">—</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="70">
                <template #default="{ row: job }">
                  <el-button link type="danger" @click="onDeleteJob(row as Company, job as Job)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else-if="jobsLoading[row.id]" description="加载中…" :image-size="48" />
            <el-empty v-else description="该公司暂无岗位，点击「添加岗位」录入" :image-size="48" />
          </div>
        </template>
      </el-table-column>
      <el-table-column label="公司" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <div class="company-name">{{ row.name }}</div>
        </template>
      </el-table-column>
      <el-table-column label="城市" width="100" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.city">{{ row.city }}</span><span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="行业" width="90" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.industry">{{ row.industry }}</span><span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="性质" width="80" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.nature">{{ row.nature }}</span><span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="官网" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <a v-if="row.website" :href="row.website" target="_blank" rel="noopener" class="link">{{ row.website }}</a>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="招聘页" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <a v-if="row.career_url" :href="row.career_url" target="_blank" rel="noopener" class="link">{{ row.career_url }}</a>
          <span v-else class="muted">未配置</span>
        </template>
      </el-table-column>
      <el-table-column label="处理状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag
            :type="row.processed ? 'success' : 'info'"
            size="small"
            effect="light"
            class="processed-tag"
            @click="toggleProcessed(row as Company)"
          >
            {{ row.processed ? '已处理' : '未处理' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openAddJob(row as Company)">添加岗位</el-button>
          <el-button
            v-if="needResolve(row as Company)"
            link
            type="primary"
            :loading="resolvingRow === row.id"
            @click="openResolve(row as Company)"
          >
            补全
          </el-button>
          <el-button link type="primary" @click="openEdit(row as Company)">编辑</el-button>
          <el-button link type="danger" @click="onDelete(row as Company)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="公司库为空，先添加目标公司">
          <el-button type="primary" @click="openCreate">添加公司</el-button>
        </el-empty>
      </template>
    </el-table>

    <!-- 底部批量操作条 -->
    <div class="list-footer">
      <span class="total-info">共 {{ items.length }} 家</span>
      <div class="footer-actions">
        <el-button :disabled="!selection.length" @click="openBatch">
          批量补全{{ selection.length ? `（${selection.length}）` : '' }}
        </el-button>
        <el-button type="danger" plain :disabled="!selection.length" @click="onBatchDelete">
          批量删除{{ selection.length ? `（${selection.length}）` : '' }}
        </el-button>
      </div>
    </div>

    <!-- 新增/编辑公司 -->
    <el-dialog v-model="formVisible" :title="editingId ? '编辑公司' : '添加公司'" width="520px" :close-on-click-modal="false">
      <el-form label-width="86px" label-position="left">
        <el-form-item label="公司名称" required>
          <el-input v-model="form.name" placeholder="必填，如：字节跳动" @input="resolveTip = ''">
            <template #append>
              <el-button
                :disabled="!form.name.trim() || resolving"
                :loading="resolving"
                @click="onAutoResolve"
              >
                自动补全
              </el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item v-if="resolveTip" label="">
          <el-alert :type="resolveTipType" :closable="false" :title="resolveTip" style="width: 100%" />
        </el-form-item>
        <el-form-item label="官网地址" required>
          <el-input v-model="form.website" placeholder="必填，如：https://www.bytedance.com" />
        </el-form-item>
        <el-form-item label="行业">
          <el-select v-model="form.industry" placeholder="可选" clearable filterable allow-create default-first-option style="width: 100%">
            <el-option v-for="i in INDUSTRIES" :key="i" :label="i" :value="i" />
          </el-select>
        </el-form-item>
        <el-form-item label="城市">
          <el-input v-model="form.city" placeholder="可选，如：北京" clearable />
        </el-form-item>
        <el-form-item label="公司性质">
          <el-select v-model="form.nature" placeholder="可选" clearable filterable allow-create default-first-option style="width: 100%">
            <el-option v-for="n in COMPANY_NATURES" :key="n" :label="n" :value="n" />
          </el-select>
        </el-form-item>
        <el-form-item label="招聘页链接">
          <el-input v-model="form.career_url" placeholder="可留空，自动补全或后续探测填写，如：https://jobs.bytedance.com/campus" />
        </el-form-item>
        <el-form-item label="处理状态">
          <el-switch v-model="form.processed" active-text="已处理" inactive-text="未处理" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="onFormSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入 txt -->
    <CompanyImportModal v-model="importVisible" @imported="onImported" />

    <!-- 批量补全 -->
    <CompanyBatchDialog
      v-model="batchVisible"
      :companies="items.filter((c) => selection.includes(c.id))"
      @done="onBatchDone"
    />

    <!-- 添加岗位 -->
    <CompanyJobFormModal
      v-if="jobFormCompany"
      v-model="jobFormVisible"
      :company="jobFormCompany"
      @submit="onJobFormSubmit"
    />

    <!-- 行级自动补全结果 -->
    <ResolveResultDialog
      v-model="resolveVisible"
      :company="resolveTarget"
      :result="resolveResult"
      @saved="onImported"
    />
  </div>
</template>

<style scoped>
.company-page {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.company-toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.toolbar-right .el-button + .el-button {
  margin-left: 0;
}
.import-help-icon {
  color: #9ca3af;
  font-size: 16px;
  cursor: help;
}
.import-help-icon:hover {
  color: #2563eb;
}
.import-help {
  max-width: 340px;
  font-size: 12px;
  line-height: 1.7;
}
.import-help p {
  margin: 0 0 4px;
}
.import-help .help-title {
  font-weight: 600;
  color: #1f2937;
  margin-top: 6px;
}
.import-help .help-title:first-child {
  margin-top: 0;
}
.import-help .help-example {
  padding: 2px 8px;
  background: #f3f4f6;
  border-radius: 4px;
  font-family: Consolas, Monaco, monospace;
  word-break: break-all;
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
.company-table {
  flex: 1;
}
.list-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}
.total-info {
  font-size: 13px;
  color: #9ca3af;
}
.footer-actions {
  display: flex;
  gap: 8px;
}
.company-name {
  font-weight: 600;
  color: #1f2937;
}
.link {
  color: #2563eb;
  text-decoration: none;
  word-break: break-all;
}
.link:hover {
  text-decoration: underline;
}
.muted {
  color: #c0c4cc;
}
.processed-tag {
  cursor: pointer;
}
.processed-tag:hover {
  opacity: 0.75;
}
.company-jobs-panel {
  padding: 4px 16px 12px 48px;
}
.jobs-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.jobs-panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.jobs-panel-count {
  font-weight: 400;
  color: #9ca3af;
  margin-left: 4px;
}
.jobs-table {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}
</style>
