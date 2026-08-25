<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import type { Company, Job, Resume } from '@/types'
import type { JobPayload } from '@/api/jobs'
import { CHANNELS, DEGREES, INDUSTRIES, JOB_TYPES } from '@/utils/normalize'
import { predictSalary } from '@/api/market'
import { ApiError } from '@/api/http'
import { buildPredictRequest } from '@/utils/market'
import type { PredictResponse } from '@/types/market'

const props = defineProps<{
  modelValue: boolean
  job: Job | null
  companies: Company[]
  resumes: Resume[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'submit', payload: JobPayload): void
}>()

interface FormModel {
  company: string
  company_id: string | null
  position: string
  job_type: string | null
  degree: string | null
  city: string
  industry: string | null
  channel: string | null
  job_url: string
  publish_date: string | null
  deadline: string | null
  resume_id: string | null
}

function emptyForm(): FormModel {
  return {
    company: '',
    company_id: null,
    position: '',
    job_type: null,
    degree: null,
    city: '',
    industry: null,
    channel: null,
    job_url: '',
    publish_date: null,
    deadline: null,
    resume_id: null,
  }
}

const formRef = ref<FormInstance>()
const form = reactive<FormModel>(emptyForm())
const submitting = ref(false)

// 市场薪资参考（P2a）
const predictLoading = ref(false)
const predictResult = ref<PredictResponse | null>(null)
const predictError = ref('')

const rules: FormRules = {
  company: [{ required: true, message: '公司名称必填', trigger: 'blur' }],
}

const companyMap = computed(() => {
  const m = new Map<string, Company>()
  for (const c of props.companies) m.set(c.name, c)
  return m
})

watch(
  () => [props.modelValue, props.job] as const,
  ([visible]) => {
    if (!visible) return
    Object.assign(form, props.job ? fromJob(props.job) : emptyForm())
    formRef.value?.clearValidate()
    // 上次的预测结果与弹窗生命周期绑定，重新打开时清空
    predictResult.value = null
    predictError.value = ''
  },
  { immediate: true },
)

function fromJob(job: Job): FormModel {
  return {
    company: job.company,
    company_id: job.company_id,
    position: job.position || '',
    job_type: job.job_type || null,
    degree: job.degree || null,
    city: job.city || '',
    industry: job.industry || null,
    channel: job.channel || null,
    job_url: job.job_url || '',
    publish_date: job.publish_date || null,
    deadline: job.deadline || null,
    resume_id: job.resume_id || null,
  }
}

function onCompanyInput(value: string) {
  const hit = companyMap.value.get(value)
  if (hit) form.company_id = hit.id
  else if (form.company_id) {
    // 改成不匹配公司库的名字时，解除关联
    const cur = props.companies.find((c) => c.id === form.company_id)
    if (cur?.name !== value) form.company_id = null
  }
}

function onCompanyIdChange(id: string | null) {
  if (id) {
    const c = props.companies.find((x) => x.id === id)
    if (c) form.company = c.name
  }
}

function close() {
  emit('update:modelValue', false)
}

/** P2a：读取表单已填字段，请求市场薪资预测并展示结果卡片 */
async function onPredict() {
  if (!form.position.trim()) {
    ElMessage.warning('请先填写岗位名称')
    return
  }
  predictLoading.value = true
  predictError.value = ''
  predictResult.value = null
  try {
    predictResult.value = await predictSalary(
      buildPredictRequest({
        position: form.position,
        city: form.city,
        degree: form.degree,
        job_type: form.job_type,
        industry: form.industry,
      }),
    )
  } catch (e) {
    const msg = e instanceof Error ? e.message : '薪资预测失败'
    predictError.value =
      e instanceof ApiError && e.status === 404 ? '市场模型未生成，运行 python -m market.cli model 后可启用' : msg
    ElMessage.error(predictError.value)
  } finally {
    predictLoading.value = false
  }
}

async function onSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const payload: JobPayload = {
      company: form.company.trim(),
      company_id: form.company_id || null,
      position: form.position.trim() || null,
      job_type: form.job_type,
      degree: form.degree,
      city: form.city.trim() || null,
      industry: form.industry,
      channel: form.channel,
      job_url: form.job_url.trim() || null,
      publish_date: form.publish_date || null,
      deadline: form.deadline || null,
      resume_id: form.resume_id || null,
    }
    emit('submit', payload)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="job ? '编辑岗位' : '新增岗位'"
    width="620px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="emit('update:modelValue', false)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px" label-position="left">
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="公司名称" prop="company">
            <el-input
              v-model="form.company"
              placeholder="必填，公司名称快照"
              clearable
              @input="onCompanyInput"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="关联公司库">
            <el-select
              v-model="form.company_id"
              placeholder="可选，关联公司库"
              clearable
              filterable
              style="width: 100%"
              @change="onCompanyIdChange"
            >
              <el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="岗位名称">
            <el-input v-model="form.position" placeholder="如：后端开发工程师" clearable />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="岗位类型">
            <el-select v-model="form.job_type" placeholder="校招/社招/实习" clearable style="width: 100%">
              <el-option v-for="t in JOB_TYPES" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="学历要求">
            <el-select v-model="form.degree" placeholder="本科/硕士/博士" clearable style="width: 100%">
              <el-option v-for="d in DEGREES" :key="d" :label="d" :value="d" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="意向城市">
            <el-input v-model="form.city" placeholder="多城市用逗号分隔，如 北京,上海" clearable />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="行业">
            <el-select
              v-model="form.industry"
              placeholder="可自定义"
              clearable
              filterable
              allow-create
              default-first-option
              style="width: 100%"
            >
              <el-option v-for="i in INDUSTRIES" :key="i" :label="i" :value="i" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="投递渠道">
            <el-select v-model="form.channel" placeholder="官网/Boss直聘等" clearable style="width: 100%">
              <el-option v-for="ch in CHANNELS" :key="ch" :label="ch" :value="ch" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="投递截止">
            <el-date-picker
              v-model="form.deadline"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="截止日期"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="发布日期">
            <el-date-picker
              v-model="form.publish_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="职位发布日期"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="JD 直链">
            <el-input v-model="form.job_url" placeholder="https://..." clearable />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="绑定简历">
            <el-select v-model="form.resume_id" placeholder="选择所投简历版本" clearable filterable style="width: 100%">
              <el-option v-for="r in resumes" :key="r.id" :label="r.name" :value="r.id" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <!-- 市场薪资参考（P2a）：模型可用时显示预测卡片，模型缺失显示生成提示 -->
    <el-card v-if="predictResult || predictError" shadow="never" class="predict-card">
      <template v-if="predictResult">
        <div class="predict-title">市场薪资参考（模型预测）</div>
        <div class="predict-avg">约 {{ predictResult.predicted_salary_avg.toLocaleString() }} 元 / 月</div>
        <div class="predict-band">参考区间：{{ predictResult.salary_band }}</div>
        <div v-if="predictResult.note" class="predict-note">{{ predictResult.note }}</div>
      </template>
      <el-alert v-else type="warning" :title="predictError" :closable="false" show-icon />
    </el-card>

    <template #footer>
      <el-button :loading="predictLoading" @click="onPredict">参考市场薪资</el-button>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="onSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.predict-card {
  margin-bottom: 4px;
}
.predict-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}
.predict-avg {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 700;
  color: #c44e52;
}
.predict-band {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
}
.predict-note {
  margin-top: 8px;
  font-size: 12px;
  color: #9ca3af;
}
</style>
