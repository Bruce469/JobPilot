<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { DataAnalysis, Files, Odometer, TrendCharts } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
const route = useRoute()

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/market')) {
    if (path.startsWith('/market/jobs')) return '/market/jobs'
    if (path.startsWith('/market/predict')) return '/market/predict'
    return '/market/dashboard'
  }
  if (path.startsWith('/board')) return '/board'
  if (path.startsWith('/jobs')) return '/jobs'
  if (path.startsWith('/companies')) return '/companies'
  if (path.startsWith('/resumes')) return '/resumes'
  if (path.startsWith('/stats')) return '/stats'
  if (path.startsWith('/settings')) return '/settings'
  return '/board'
})

const backendState = computed(() => {
  if (appStore.booting) return { text: '连接后端中…', type: 'info' as const }
  if (appStore.booted) return { text: '后端已连接', type: 'success' as const }
  return { text: '后端未连接', type: 'danger' as const }
})

onMounted(() => {
  if (!appStore.booted) {
    void appStore.boot()
  }
})

function retryBoot() {
  void appStore.boot()
}
</script>

<template>
  <el-container class="app-shell">
    <el-aside width="200px" class="app-aside">
      <div class="app-logo">
        <div class="logo-title">JobPilot</div>
        <div class="logo-sub">秋招投递 · 市场情报 · v{{ appStore.appVersion }}</div>
      </div>
      <el-menu :default-active="activeMenu" :default-openeds="['market']" router class="app-menu">
        <el-menu-item index="/board">看板</el-menu-item>
        <el-menu-item index="/jobs">岗位列表</el-menu-item>
        <el-menu-item index="/companies">公司库</el-menu-item>
        <el-menu-item index="/resumes">简历</el-menu-item>
        <el-menu-item index="/stats">统计</el-menu-item>
        <el-sub-menu index="market">
          <template #title>
            <el-icon><DataAnalysis /></el-icon>
            <span>市场情报</span>
          </template>
          <el-menu-item index="/market/dashboard">
            <el-icon><Odometer /></el-icon>
            <span>情报看板</span>
          </el-menu-item>
          <el-menu-item index="/market/jobs">
            <el-icon><Files /></el-icon>
            <span>市场岗位库</span>
          </el-menu-item>
          <el-menu-item index="/market/predict">
            <el-icon><TrendCharts /></el-icon>
            <span>薪资预测</span>
          </el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/settings">设置</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="app-body">
      <el-header class="app-header">
        <div class="header-left">
          <span class="header-path">{{ route.meta.title ?? '' }}</span>
        </div>
        <div class="header-right">
          <el-alert
            v-if="appStore.booted && appStore.backup.need_backup && !appStore.backupAlertDismissed"
            class="backup-alert"
            type="warning"
            :closable="true"
            show-icon
            @close="appStore.dismissBackupAlert"
          >
            <span class="backup-alert-text">
              距上次导出备份已 {{ appStore.backup.days_since ?? '?' }} 天，建议前往「设置」导出备份
            </span>
          </el-alert>
          <el-tag :type="backendState.type" size="small" effect="light">{{ backendState.text }}</el-tag>
        </div>
      </el-header>

      <el-main class="app-main">
        <div v-if="!appStore.booted && appStore.booting" class="boot-state" v-loading="true" element-loading-text="正在连接后端服务…"></div>
        <div v-else-if="!appStore.booted && appStore.bootError" class="boot-error">
          <el-result icon="error" title="无法连接后端服务" :sub-title="appStore.bootError">
            <template #extra>
              <p class="boot-hint">请先启动后端：在 backend 目录执行 <code>python run.py</code>（默认 127.0.0.1:8000）。</p>
              <el-button type="primary" @click="retryBoot">重试</el-button>
            </template>
          </el-result>
        </div>
        <router-view v-else />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-shell {
  height: 100%;
}
.app-aside {
  background: #fff;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
}
.app-logo {
  padding: 16px;
  border-bottom: 1px solid #f3f4f6;
}
.logo-title {
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
}
.logo-sub {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 2px;
}
.app-menu {
  border-right: none;
  flex: 1;
}
.app-body {
  min-width: 0;
}
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  height: 52px;
}
.header-left {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.backup-alert {
  padding: 4px 12px;
  border-radius: 6px;
}
.backup-alert-text {
  font-size: 12px;
}
.app-main {
  background: #f7f8fa;
  padding: 16px;
  overflow: auto;
}
.boot-state {
  height: 100%;
}
.boot-error {
  max-width: 560px;
  margin: 60px auto;
}
.boot-hint {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 12px;
}
.boot-hint code {
  background: #f3f4f6;
  border-radius: 4px;
  padding: 1px 6px;
}
</style>
