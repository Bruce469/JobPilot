<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useCompaniesStore } from '@/stores/companies'
import type { Company, CompanyResolveResult } from '@/types'
import { INDUSTRIES } from '@/utils/normalize'

const props = defineProps<{
  modelValue: boolean
  company: Company | null
  result: CompanyResolveResult | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'saved'): void
}>()

const companiesStore = useCompaniesStore()

const form = reactive({ website: '', industry: '', career_url: '' })
const saving = ref(false)

watch(
  () => props.modelValue,
  (v) => {
    if (!v || !props.result || !props.company) return
    // 补全结果优先，缺失字段回退公司已有值
    form.website = props.result.website || props.company.website || ''
    form.industry = props.result.industry || props.company.industry || ''
    form.career_url = props.result.career_url || props.company.career_url || ''
  },
)

async function onSave() {
  if (!props.company) return
  saving.value = true
  try {
    const payload: Record<string, string | null> = {
      industry: form.industry.trim() || null,
      career_url: form.career_url.trim() || null,
    }
    if (form.website.trim()) payload.website = form.website.trim()
    await companiesStore.updateCompany(props.company.id, payload)
    ElMessage.success('补全结果已保存')
    emit('saved')
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="`补全结果 - ${company?.name ?? ''}`"
    width="520px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-alert
      v-if="result?.source === 'failed'"
      type="error"
      :closable="false"
      :title="`自动补全失败：${result.error || '未命中映射且搜索失败'}`"
      description="可手动填写下方字段后保存，稍后再次尝试补全。"
      class="result-alert"
    />
    <el-alert
      v-else-if="result?.source === 'search'"
      type="warning"
      :closable="false"
      title="结果来自网络搜索，请核对后再保存"
      class="result-alert"
    />
    <el-alert
      v-else-if="result?.source === 'mapping'"
      type="success"
      :closable="false"
      title="已命中内置映射表，可编辑后保存"
      class="result-alert"
    />

    <el-form label-width="86px" label-position="left">
      <el-form-item label="官网地址">
        <el-input v-model="form.website" placeholder="如：https://www.bytedance.com" />
      </el-form-item>
      <el-form-item label="行业">
        <el-select
          v-model="form.industry"
          placeholder="可选"
          clearable
          filterable
          allow-create
          default-first-option
          style="width: 100%"
        >
          <el-option v-for="i in INDUSTRIES" :key="i" :label="i" :value="i" />
        </el-select>
      </el-form-item>
      <el-form-item label="招聘页链接">
        <el-input v-model="form.career_url" placeholder="如：https://jobs.bytedance.com/campus" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button :disabled="saving" @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.result-alert {
  margin-bottom: 14px;
}
</style>
