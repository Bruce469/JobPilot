<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getResume } from '@/api/resumes'
import type { Resume } from '@/types'
import ResumeRenderer from '@/components/ResumeRenderer.vue'

const route = useRoute()
const router = useRouter()
const resumeId = route.params.id as string

const resume = ref<Resume | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    resume.value = await getResume(resumeId)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载简历失败')
    router.push('/resumes')
  } finally {
    loading.value = false
  }
})

function onPrint() {
  window.print()
}
</script>

<template>
  <div v-loading="loading" class="preview-page">
    <div class="preview-toolbar no-print">
      <div class="toolbar-left">
        <el-button @click="router.push('/resumes')">返回</el-button>
        <el-button @click="router.push(`/resumes/${resumeId}`)">返回编辑</el-button>
      </div>
      <div class="toolbar-right">
        <el-button type="primary" @click="onPrint">打印 / 导出 PDF</el-button>
      </div>
    </div>

    <div class="print-area">
      <ResumeRenderer v-if="resume" :resume="resume" />
    </div>
  </div>
</template>

<style scoped>
.preview-page {
  padding-bottom: 40px;
}
.preview-toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}
.toolbar-left {
  display: flex;
  gap: 8px;
}
.print-area {
  background: #e5e7eb;
  border-radius: 4px;
  padding: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  overflow-x: auto;
}
</style>

<style>
/* 打印样式：仅打印简历区域，A4 版式 */
@media print {
  @page {
    size: A4;
    margin: 0;
  }
  .no-print {
    display: none !important;
  }
  body * {
    visibility: hidden;
  }
  .print-area,
  .print-area * {
    visibility: visible;
  }
  .print-area {
    position: absolute;
    left: 0;
    top: 0;
    width: 210mm;
    padding: 0;
    background: #fff;
    box-shadow: none;
    border-radius: 0;
  }
  .resume-page {
    width: 210mm;
    min-height: 297mm;
    box-shadow: none;
  }
}
</style>
