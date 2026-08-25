<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { predictSalary } from '@/api/market'
import { ApiError } from '@/api/http'
import type { PredictResponse } from '@/types/market'

const formRef = ref<FormInstance>()
const form = reactive({
  job_title: '数据分析师',
  city: '北京',
  job_category: '数据分析',
  education_req: '本科',
  experience_req: '1-3年',
  job_type: '社招',
  industry: '互联网',
  company_size: '1000-5000人',
  skills: 'SQL, Python, Excel',
})

const CATEGORIES = ['数据分析', '数据科学', '大数据', '算法', 'BI数仓']
const EDUCATIONS = ['不限', '大专', '本科', '硕士', '博士']
const EXPERIENCES = ['不限', '1年以内', '1-3年', '3-5年', '5-10年', '10年以上']
const JOB_TYPES = ['社招', '校招', '实习']
const COMPANY_SIZES = ['50人以下', '50-150人', '150-500人', '500-1000人', '1000-5000人', '5000-10000人', '10000人以上']

const rules: FormRules = {
  job_title: [{ required: true, message: '请输入岗位标题', trigger: 'blur' }],
  city: [{ required: true, message: '请输入城市', trigger: 'blur' }],
}

// 模型文件缺失时 B 后端返回 404，给出可执行的生成提示
const MODEL_MISSING_HINT = '模型文件缺失，请先运行 python -m market.cli model 生成模型'

const result = ref<PredictResponse | null>(null)
const error = ref('')
const loading = ref(false)

async function submit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  error.value = ''
  result.value = null
  const payload = {
    job_title: form.job_title.trim(),
    city: form.city.trim(),
    job_category: form.job_category,
    education_req: form.education_req,
    experience_req: form.experience_req,
    job_type: form.job_type,
    industry: form.industry.trim() || '其他',
    company_size: form.company_size || null,
    skills: form.skills.split(/[,，、\s]+/).filter(Boolean),
  }
  try {
    result.value = await predictSalary(payload)
  } catch (e) {
    const msg = e instanceof Error ? e.message : '预测失败'
    error.value = e instanceof ApiError && e.status === 404 ? MODEL_MISSING_HINT : msg
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="predict-page">
    <div class="predict-form">
      <h3 class="form-title">薪资在线预测（XGBoost）</h3>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="88px" label-position="left">
        <el-form-item label="岗位标题" prop="job_title">
          <el-input v-model="form.job_title" placeholder="如 数据分析师" />
        </el-form-item>
        <el-form-item label="城市" prop="city">
          <el-input v-model="form.city" placeholder="不带市后缀，如 北京" />
        </el-form-item>
        <el-form-item label="岗位类别">
          <el-select v-model="form.job_category" class="full">
            <el-option v-for="c in CATEGORIES" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="学历要求">
          <el-select v-model="form.education_req" class="full">
            <el-option v-for="e in EDUCATIONS" :key="e" :label="e" :value="e" />
          </el-select>
        </el-form-item>
        <el-form-item label="经验要求">
          <el-select v-model="form.experience_req" class="full">
            <el-option v-for="e in EXPERIENCES" :key="e" :label="e" :value="e" />
          </el-select>
        </el-form-item>
        <el-form-item label="岗位类型">
          <el-select v-model="form.job_type" class="full">
            <el-option v-for="t in JOB_TYPES" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="行业">
          <el-input v-model="form.industry" placeholder="如 互联网" />
        </el-form-item>
        <el-form-item label="公司规模">
          <el-select v-model="form.company_size" clearable class="full">
            <el-option v-for="s in COMPANY_SIZES" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="技能关键词">
          <el-input v-model="form.skills" placeholder="逗号分隔，如 SQL, Python" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="full" :loading="loading" @click="submit">
            {{ loading ? '预测中…' : '开始预测' }}
          </el-button>
        </el-form-item>
      </el-form>
      <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" />
    </div>

    <div v-if="result" class="predict-result">
      <h3 class="form-title">预测结果</h3>
      <div class="result-big">{{ result.predicted_salary_avg.toLocaleString() }} 元/月</div>
      <div class="result-band">参考区间：{{ result.salary_band }}</div>
      <div class="result-note">{{ result.note }}</div>
    </div>
  </div>
</template>

<style scoped>
.predict-page {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  flex-wrap: wrap;
}
.predict-form {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 20px 24px;
  width: 440px;
}
.form-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 16px;
}
.full {
  width: 100%;
}
.predict-result {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 20px 24px;
  min-width: 280px;
}
.result-big {
  font-size: 34px;
  font-weight: 700;
  color: #c44e52;
}
.result-band {
  margin-top: 8px;
  color: #6b7280;
  font-size: 14px;
}
.result-note {
  margin-top: 14px;
  color: #9ca3af;
  font-size: 12px;
}
</style>
