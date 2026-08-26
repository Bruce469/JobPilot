<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useCompaniesStore } from '@/stores/companies'
import type { Company, CompanyResolveResult, FetchTaskResult, ProbeCandidate } from '@/types'
import { COMPANY_NATURES, INDUSTRIES, PROBE_STATUSES } from '@/utils/normalize'
import { formatDateTime } from '@/utils/date'
import ProbeResultPanel from '@/components/ProbeResultPanel.vue'
import FetchPreviewModal from '@/components/FetchPreviewModal.vue'
import CompanyImportModal from '@/components/CompanyImportModal.vue'
import CompanyBatchDialog from '@/components/CompanyBatchDialog.vue'
import ResolveResultDialog from '@/components/ResolveResultDialog.vue'

const companiesStore = useCompaniesStore()
const { items, loading } = storeToRefs(companiesStore)

// 每公司当前运行的任务状态文本
const running = reactive<Record<string, string>>({})

function isRunning(id: string) {
  return !!running[id]
}

// ---------------- 导入 txt ----------------
const importVisible = ref(false)

// ---------------- 批量操作 ----------------
const selection = ref<string[]>([])
const batchVisible = ref(false)
const batchMode = ref<'probe' | 'resolve'>('probe')

function onSelectionChange(rows: Company[]) {
  selection.value = rows.map((r) => r.id)
}

function openBatch(mode: 'probe' | 'resolve') {
  batchMode.value = mode
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

// ---------------- 筛选 ----------------
interface CompanyFilterState {
  keyword: string
  city: string
  industry: string | null
  nature: string | null
}

const filters = reactive<CompanyFilterState>({ keyword: '', city: '', industry: null, nature: null })

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
  Object.assign(filters, { keyword: '', city: '', industry: null, nature: null })
  void load()
}

// ---------------- 列表加载 ----------------
async function load() {
  try {
    await companiesStore.fetchCompanies({
      city: filters.city || null,
      industry: filters.industry || null,
      nature: filters.nature || null,
      keyword: filters.keyword || null,
    })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载公司库失败')
  }
}
onMounted(load)

// ---------------- 新增 / 编辑 ----------------
interface CompanyForm {
  name: string
  website: string
  industry: string | null
  city: string
  nature: string | null
  career_url: string
  notes: string
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
})

// 名称自动补全
const resolving = ref(false)
const resolveTip = ref('')
const resolveTipType = ref<'success' | 'warning' | 'info'>('info')

function openCreate() {
  editingId.value = null
  Object.assign(form, { name: '', website: '', industry: null, city: '', nature: null, career_url: '', notes: '' })
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

// ---------------- 探测 / 抓取 ----------------
const probeVisible = ref(false)
const probeResult = ref<{ companyId: string; candidates: ProbeCandidate[] } | null>(null)

const fetchVisible = ref(false)
const fetchResult = ref<{ company: Company; result: FetchTaskResult } | null>(null)

async function startProbe(c: Company) {
  running[c.id] = '探测中'
  try {
    const jobId = await companiesStore.probe(c.id)
    const task = await companiesStore.pollTask(jobId, {
      onProgress: (t) => {
        running[c.id] = `探测中：${t.progress || ''}`
      },
    })
    await companiesStore.fetchCompanies()
    if (task.result?.candidates?.length) {
      probeResult.value = { companyId: c.id, candidates: task.result.candidates }
      probeVisible.value = true
    } else {
      ElMessage.warning('未发现招聘入口，可在编辑中手动填写 career_url')
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '探测失败')
    await companiesStore.fetchCompanies()
  } finally {
    delete running[c.id]
  }
}

async function startFetch(c: Company, careerUrl?: string) {
  running[c.id] = '抓取中'
  try {
    const jobId = await companiesStore.fetchJobs(c.id, careerUrl ?? c.career_url ?? undefined)
    const task = await companiesStore.pollTask(jobId, {
      onProgress: (t) => {
        running[c.id] = `抓取中：${t.progress || ''}`
      },
    })
    await companiesStore.fetchCompanies()
    if (task.status === 'done' && task.result?.count && task.result.job_candidates?.length) {
      fetchResult.value = { company: c, result: task.result }
      fetchVisible.value = true
    } else if (task.status === 'done') {
      ElMessage.warning('解析到 0 条岗位，请手动录入')
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '抓取失败')
    await companiesStore.fetchCompanies()
  } finally {
    delete running[c.id]
  }
}

async function onProbeSelect(url: string) {
  if (!probeResult.value) return
  const companyId = probeResult.value.companyId
  probeVisible.value = false
  try {
    const c = await companiesStore.updateCompany(companyId, { career_url: url })
    ElMessage.success('已保存招聘页链接')
    const doFetch = await ElMessageBox.confirm('是否立即抓取该招聘页的岗位？', '抓取岗位', {
      confirmButtonText: '立即抓取',
      cancelButtonText: '稍后',
      type: 'info',
    })
      .then(() => true)
      .catch(() => false)
    if (doFetch) await startFetch(c, url)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存链接失败')
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

function probeStatusType(status: string | null): 'success' | 'info' | 'warning' | 'danger' {
  if (status === '成功') return 'success'
  if (status === '未探测') return 'info'
  if (status === '需人工') return 'warning'
  if (status === '失败') return 'danger'
  return 'info'
}
</script>

<template>
  <div class="company-page">
    <div class="company-toolbar">
      <el-button :loading="loading" @click="load">刷新</el-button>
      <div class="toolbar-right">
        <el-button @click="importVisible = true">导入 txt</el-button>
        <el-button type="primary" @click="openCreate">添加公司</el-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input v-model="filters.keyword" placeholder="公司名关键词" clearable class="filter-item keyword" @keyup.enter="requestFetch" />
      <el-input v-model="filters.city" placeholder="城市" clearable class="filter-item" @keyup.enter="requestFetch" />
      <el-select v-model="filters.industry" placeholder="行业" clearable filterable allow-create default-first-option class="filter-item">
        <el-option v-for="i in INDUSTRIES" :key="i" :label="i" :value="i" />
      </el-select>
      <el-select v-model="filters.nature" placeholder="公司性质" clearable filterable allow-create default-first-option class="filter-item">
        <el-option v-for="n in COMPANY_NATURES" :key="n" :label="n" :value="n" />
      </el-select>
      <el-button @click="clearFilters">清除筛选</el-button>
      <el-button :loading="loading" @click="load">搜索</el-button>
    </div>

    <el-table v-loading="loading" :data="items" row-key="id" class="company-table" @selection-change="onSelectionChange">
      <el-table-column type="selection" width="44" />
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
      <el-table-column label="探测状态" width="90">
        <template #default="{ row }">
          <el-tag :type="probeStatusType(row.probe_status)" size="small" effect="light">
            {{ row.probe_status || '未探测' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="ATS" width="80">
        <template #default="{ row }">
          <span v-if="row.ats_type">{{ row.ats_type }}</span><span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="最近抓取" min-width="170" show-overflow-tooltip>
        <template #default="{ row }">
          <div v-if="row.last_fetch_result" class="fetch-result">{{ row.last_fetch_result }}</div>
          <div v-if="row.last_fetched_at" class="fetch-time">{{ formatDateTime(row.last_fetched_at) }}</div>
          <span v-if="!row.last_fetch_result" class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <template v-if="isRunning(row.id)">
            <el-tag type="warning" size="small" effect="dark">{{ running[row.id] }}</el-tag>
          </template>
          <template v-else>
            <el-button link type="primary" :disabled="isRunning(row.id)" @click="startProbe(row as Company)">探测</el-button>
            <el-button link type="primary" :disabled="isRunning(row.id) || !row.career_url" @click="startFetch(row as Company)">
              抓取
            </el-button>
            <el-button
              v-if="needResolve(row as Company)"
              link
              type="primary"
              :loading="resolvingRow === row.id"
              :disabled="isRunning(row.id)"
              @click="openResolve(row as Company)"
            >
              补全
            </el-button>
            <el-button link type="primary" @click="openEdit(row as Company)">编辑</el-button>
            <el-button link type="danger" @click="onDelete(row as Company)">删除</el-button>
          </template>
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
        <el-button :disabled="!selection.length" @click="openBatch('resolve')">
          批量补全{{ selection.length ? `（${selection.length}）` : '' }}
        </el-button>
        <el-button :disabled="!selection.length" @click="openBatch('probe')">
          批量探测{{ selection.length ? `（${selection.length}）` : '' }}
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
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="onFormSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 探测结果 -->
    <ProbeResultPanel
      v-if="probeResult"
      v-model="probeVisible"
      :company-name="items.find((c) => c.id === probeResult?.companyId)?.name ?? ''"
      :candidates="probeResult.candidates"
      @select="onProbeSelect"
    />

    <!-- 抓取预览导入 -->
    <FetchPreviewModal
      v-if="fetchResult"
      v-model="fetchVisible"
      :company-id="fetchResult.company.id"
      :company-name="fetchResult.company.name"
      :result="fetchResult.result"
      @imported="onImported"
    />

    <!-- 批量导入 txt -->
    <CompanyImportModal v-model="importVisible" @imported="onImported" />

    <!-- 批量探测 / 批量补全 -->
    <CompanyBatchDialog
      v-model="batchVisible"
      :mode="batchMode"
      :companies="items.filter((c) => selection.includes(c.id))"
      @done="onBatchDone"
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
.fetch-result {
  font-size: 12px;
  color: #374151;
}
.fetch-time {
  font-size: 11px;
  color: #9ca3af;
}
</style>
