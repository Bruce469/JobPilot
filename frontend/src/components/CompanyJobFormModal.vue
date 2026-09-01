<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { type FormInstance, type FormRules } from 'element-plus'
import type { Company } from '@/types'
import type { JobPayload } from '@/api/jobs'
import { CHANNELS, DEGREES, JOB_TYPES } from '@/utils/normalize'

const props = defineProps<{
  modelValue: boolean
  company: Company
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'submit', payload: JobPayload): void
}>()

interface FormModel {
  position: string
  job_type: string | null
  degree: string | null
  city: string
  channel: string | null
  job_url: string
  deadline: string | null
}

const formRef = ref<FormInstance>()
const form = reactive<FormModel>({
  position: '',
  job_type: null,
  degree: null,
  city: '',
  channel: null,
  job_url: '',
  deadline: null,
})

const rules: FormRules = {
  position: [{ required: true, message: '岗位名称必填', trigger: 'blur' }],
}

watch(
  () => props.modelValue,
  (v) => {
    if (!v) return
    Object.assign(form, { position: '', job_type: null, degree: null, city: '', channel: null, job_url: '', deadline: null })
    formRef.value?.clearValidate()
  },
)

async function onSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  emit('submit', {
    company: props.company.name,
    company_id: props.company.id,
    position: form.position.trim(),
    job_type: form.job_type,
    degree: form.degree,
    city: form.city.trim() || null,
    industry: props.company.industry, // 自动带入公司行业
    channel: form.channel,
    job_url: form.job_url.trim() || null,
    deadline: form.deadline || null,
  })
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="`为「${company.name}」添加岗位`"
    width="560px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="emit('update:modelValue', false)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px" label-position="left">
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="岗位名称" prop="position">
            <el-input v-model="form.position" placeholder="必填，如：后端开发工程师" clearable />
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
          <el-form-item label="工作城市">
            <el-input v-model="form.city" placeholder="如：成都" clearable />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="投递渠道">
            <el-select v-model="form.channel" placeholder="官网/Boss直聘等" clearable style="width: 100%">
              <el-option v-for="ch in CHANNELS" :key="ch" :label="ch" :value="ch" />
            </el-select>
          </el-form-item>
        </el-col>
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
      </el-row>

      <el-form-item label="JD 直链">
        <el-input v-model="form.job_url" placeholder="https://..." clearable />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="onSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>
