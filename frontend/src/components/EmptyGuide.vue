<script setup lang="ts">
// 首次使用空态引导：添加公司 → 探测 → 抓取 → 导入 → 投递
const steps = [
  { title: '添加目标公司', desc: '在公司库录入公司名称与官网地址', to: '/companies' },
  { title: '探测招聘入口', desc: '自动解析官网招聘页（careers/jobs 入口）', to: '/companies' },
  { title: '抓取岗位列表', desc: '从招聘页解析公开岗位字段', to: '/companies' },
  { title: '勾选导入岗位', desc: '按公司+岗位去重后导入岗位库', to: '/jobs' },
  { title: '推进投递状态', desc: '在看板拖拽卡片或按钮流转状态', to: '/board' },
]
</script>

<template>
  <div class="empty-guide">
    <h2 class="guide-title">还没有岗位数据，按以下流程开始使用</h2>
    <div class="guide-steps">
      <div v-for="(s, i) in steps" :key="i" class="guide-step">
        <div class="step-num">{{ i + 1 }}</div>
        <div class="step-body">
          <div class="step-title">{{ s.title }}</div>
          <div class="step-desc">{{ s.desc }}</div>
        </div>
        <router-link :to="s.to" class="step-link">前往</router-link>
      </div>
    </div>
    <div class="guide-actions">
      <router-link to="/companies"><el-button type="primary">去公司库添加公司</el-button></router-link>
      <router-link to="/jobs"><el-button plain>直接手动录入岗位</el-button></router-link>
    </div>
  </div>
</template>

<style scoped>
.empty-guide {
  text-align: center;
  padding: 32px 16px;
}
.guide-title {
  font-size: 16px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 20px;
}
.guide-steps {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px;
  max-width: 880px;
  margin: 0 auto 24px;
}
.guide-step {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px 14px;
  width: 250px;
  text-align: left;
}
.step-num {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.step-body {
  flex: 1;
}
.step-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}
.step-desc {
  font-size: 11px;
  color: #6b7280;
  margin-top: 2px;
}
.step-link {
  font-size: 12px;
  color: #2563eb;
  text-decoration: none;
  white-space: nowrap;
}
.step-link:hover {
  text-decoration: underline;
}
.guide-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}
</style>
