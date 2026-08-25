<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useResumesStore } from '@/stores/resumes'
import { formatDateTime } from '@/utils/date'
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
      const force = await ElMessageBox.confirm(
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
</script>

<template>
  <div class="resume-list-page">
    <div class="resume-toolbar">
      <el-button :loading="loading" @click="load">刷新</el-button>
      <div class="toolbar-right">
        <el-button type="primary" @click="onCreate">新建简历</el-button>
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
      <el-table-column label="操作" width="170" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/resumes/${row.id}`)">编辑</el-button>
          <el-button link type="primary" @click="router.push(`/resumes/${row.id}/preview`)">预览</el-button>
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
.resume-footer {
  margin-top: 12px;
  font-size: 12px;
}
</style>
