<script setup lang="ts">
// 简历源 PDF 在线预览弹窗：iframe 无法携带 X-Auth-Token 请求头，
// 因此用 axios 以 responseType:'blob' 拉取后转 objectURL 再展示，关闭时 revoke 避免内存泄漏。
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ApiError } from '@/api/http'
import { getResumePdfBlob } from '@/api/resumes'

const props = defineProps<{
  modelValue: boolean
  resumeId: string
  title?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()

const loading = ref(false)
const objectUrl = ref('')
const frameSrc = ref('')

watch(
  () => props.modelValue,
  async (visible) => {
    if (!visible) return
    loading.value = true
    try {
      const blob = await getResumePdfBlob(props.resumeId)
      // 拉取期间用户已关闭弹窗：尚未创建 objectURL，直接返回（blob 由 GC 回收）
      if (!props.modelValue) return
      const url = URL.createObjectURL(blob)
      objectUrl.value = url
      frameSrc.value = url
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        ElMessage.error('该简历没有源 PDF 文件')
      } else {
        ElMessage.error(e instanceof Error ? e.message : '加载 PDF 失败')
      }
    } finally {
      loading.value = false
    }
  },
)

/** 关闭时 revoke objectURL 并清空 iframe src */
function release() {
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value)
    objectUrl.value = ''
  }
  frameSrc.value = ''
}

function onOpenInNewWindow() {
  if (objectUrl.value) window.open(objectUrl.value, '_blank')
}

function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title || '源 PDF 预览'"
    width="72%"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="release"
  >
    <div v-loading="loading" class="pdf-body">
      <div v-if="frameSrc" class="pdf-toolbar">
        <span class="muted">预览为只读；如需缩放 / 复制等能力请「新窗口打开」</span>
        <el-button link type="primary" @click="onOpenInNewWindow">新窗口打开</el-button>
      </div>
      <iframe v-if="frameSrc" :src="frameSrc" title="源 PDF 预览" class="pdf-frame" />
      <el-empty v-if="!loading && !frameSrc" description="PDF 加载失败或暂无源文件" :image-size="60" />
    </div>
    <template #footer>
      <el-button @click="close">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.pdf-body {
  min-height: 200px;
}
.pdf-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.pdf-frame {
  width: 100%;
  height: 70vh;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  background: #f9fafb;
}
.muted {
  color: #9ca3af;
  font-size: 12px;
}
</style>
