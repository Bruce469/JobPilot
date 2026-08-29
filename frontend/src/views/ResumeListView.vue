<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type UploadFile, type UploadRawFile, type UploadUserFile } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useResumesStore } from '@/stores/resumes'
import { uploadResumePdf } from '@/api/resumes'
import { formatDateTime } from '@/utils/date'
import PdfViewerDialog from '@/components/PdfViewerDialog.vue'
import type { Resume } from '@/types'

const router = useRouter()
const resumesStore = useResumesStore()
const { items, loading } = storeToRefs(resumesStore)

async function load() {
  try {
    await resumesStore.fetchResumes()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载简历失败')
  }
}
onMounted(load)

async function onCreate() {
  try {
    const r = await resumesStore.createResume({
      name: '未命名简历',
      basic: { name: '', phone: '', email: '', target_position: '', city: '' },
    })
    router.push(`/resumes/${r.id}`)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '创建简历失败')
  }
}

async function onDelete(r: Resume) {
  try {
    await ElMessageBox.confirm(`确认删除简历「${r.name}」？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
    })
    const result = await resumesStore.deleteResume(r.id, false)
    if (result && result.referenced_by > 0) {
      // force 变量曾误接收 ElMessageBox 的返回值（无意义），直接丢弃
      await ElMessageBox.confirm(
        `该简历已被 ${result.referenced_by} 个岗位绑定，删除后这些岗位的绑定将置空。确认删除？`,
        '简历被引用',
        {
          type: 'warning',
          confirmButtonText: '仍要删除',
          cancelButtonText: '取消',
        },
      )
      await resumesStore.deleteResume(r.id, true)
    }
    ElMessage.success('已删除')
  } catch {
    // 取消
  }
}

// ---------------- 上传 PDF 简历 ----------------
/** 与后端 upload-pdf 限制一致，前端先行拦截给友好提示 */
const MAX_PDF_SIZE = 10 * 1024 * 1024
const uploadVisible = ref(false)
const uploading = ref(false)
const uploadFile = ref<File | null>(null)
const fileList = ref<UploadUserFile[]>([])

watch(uploadVisible, (v) => {
  if (!v) return
  // 重新打开时清空上一次的文件
  uploadFile.value = null
  fileList.value = []
  uploading.value = false
})

function onUploadChange(item: UploadFile) {
  const raw = item.raw
  if (!raw) return
  if (raw.size > MAX_PDF_SIZE) {
    ElMessage.error('PDF 文件超过 10MB，无法上传，请更换文件')
    uploadFile.value = null
    fileList.value = []
    return
  }
  uploadFile.value = raw
}

/** limit=1 已选 1 个后再选新文件走 on-exceed：替换为新文件 */
function onUploadExceed(files: File[]) {
  const f = files[0]
  if (!f) return
  if (f.size > MAX_PDF_SIZE) {
    ElMessage.error('PDF 文件超过 10MB，无法上传，请更换文件')
    return
  }
  uploadFile.value = f
  fileList.value = [{ name: f.name, raw: f as UploadRawFile }]
}

function onUploadRemove() {
  uploadFile.value = null
}

async function onUploadCreate() {
  if (!uploadFile.value) {
    ElMessage.warning('请先选择 PDF 文件')
    return
  }
  uploading.value = true
  try {
    const r = await uploadResumePdf(uploadFile.value)
    ElMessage.success('PDF 简历创建成功')
    uploadVisible.value = false
    // 返回值插入列表顶部，返回列表时无需手动刷新
    if (!items.value.some((x) => x.id === r.id)) items.value.unshift(r)
    router.push(`/resumes/${r.id}`)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '上传失败')
  } finally {
    uploading.value = false
  }
}

// ---------------- 源 PDF 预览 ----------------
const viewerVisible = ref(false)
const viewerResumeId = ref('')
function onViewPdf(r: Resume) {
  viewerResumeId.value = r.id
  viewerVisible.value = true
}
</script>

<template>
  <div class="resume-list-page">
    <div class="resume-toolbar">
      <el-button :loading="loading" @click="load">刷新</el-button>
      <div class="toolbar-right">
        <el-dropdown split-button type="primary" trigger="click" @click="onCreate">
          新建简历
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="uploadVisible = true">上传 PDF 简历</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <el-table v-loading="loading" :data="items" row-key="id" class="resume-table">
      <el-table-column label="简历名称" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="resume-name">{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="姓名" width="110">
        <template #default="{ row }">
          <span v-if="row.basic?.name">{{ row.basic.name }}</span><span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="意向岗位" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.basic?.target_position">{{ row.basic.target_position }}</span><span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="区块数" width="90">
        <template #default="{ row }">
          {{ (row.education?.length || 0) + (row.experience?.length || 0) + (row.projects?.length || 0) }}
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="150">
        <template #default="{ row }">
          <span class="muted">{{ formatDateTime(row.updated_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/resumes/${row.id}`)">编辑</el-button>
          <el-button link type="primary" @click="router.push(`/resumes/${row.id}/preview`)">预览</el-button>
          <el-button v-if="row.pdf_file" link type="primary" @click="onViewPdf(row as Resume)">源PDF</el-button>
          <el-button link type="danger" @click="onDelete(row as Resume)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无简历，点击「新建简历」开始维护">
          <el-button type="primary" @click="onCreate">新建简历</el-button>
        </el-empty>
      </template>
    </el-table>

    <div class="resume-footer">
      <span class="muted">提示：简历可与岗位绑定（在岗位编辑中选择「绑定简历」），并支持 A4 打印/导出 PDF。</span>
    </div>

    <!-- 上传 PDF 创建简历 -->
    <el-dialog v-model="uploadVisible" title="上传 PDF 简历" width="520px" append-to-body :close-on-click-modal="false">
      <el-upload
        v-model:file-list="fileList"
        drag
        accept=".pdf"
        :auto-upload="false"
        :limit="1"
        :on-change="onUploadChange"
        :on-exceed="onUploadExceed"
        :on-remove="onUploadRemove"
      >
        <div class="upload-icon">PDF</div>
        <div class="upload-text">将 PDF 拖到此处，或<em>点击选择文件</em></div>
        <template #tip>
          <div class="el-upload__tip">
            仅支持 .pdf，大小不超过 10MB；上传成功后自动创建简历并进入编辑页补录结构化内容。
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button :disabled="uploading" @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!uploadFile" @click="onUploadCreate">
          上传并创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 源 PDF 在线预览 -->
    <PdfViewerDialog v-model="viewerVisible" :resume-id="viewerResumeId" title="源 PDF 预览" />
  </div>
</template>

<style scoped>
.resume-list-page {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.resume-toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}
.resume-table {
  flex: 1;
}
.resume-name {
  font-weight: 600;
  color: #1f2937;
}
.muted {
  color: #c0c4cc;
}
.upload-icon {
  font-size: 26px;
  font-weight: 700;
  color: #c44e52;
  margin-bottom: 6px;
}
.upload-text {
  font-size: 13px;
  color: #6b7280;
}
.resume-footer {
  margin-top: 12px;
  font-size: 12px;
}
</style>
