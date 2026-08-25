import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/board' },
    { path: '/board', name: 'board', component: () => import('@/views/BoardView.vue'), meta: { title: '看板' } },
    { path: '/jobs', name: 'jobs', component: () => import('@/views/ListView.vue'), meta: { title: '岗位列表' } },
    { path: '/companies', name: 'companies', component: () => import('@/views/CompanyView.vue'), meta: { title: '公司库' } },
    { path: '/resumes', name: 'resumes', component: () => import('@/views/ResumeListView.vue'), meta: { title: '简历' } },
    { path: '/resumes/:id', name: 'resume-edit', component: () => import('@/views/ResumeEditView.vue'), meta: { title: '编辑简历' } },
    {
      path: '/resumes/:id/preview',
      name: 'resume-preview',
      component: () => import('@/views/ResumePreviewView.vue'),
      meta: { title: '简历预览' },
    },
    { path: '/stats', name: 'stats', component: () => import('@/views/StatsView.vue'), meta: { title: '统计' } },
    {
      path: '/market',
      redirect: '/market/dashboard',
      meta: { title: '市场情报' },
    },
    {
      path: '/market/dashboard',
      name: 'market-dashboard',
      component: () => import('@/views/MarketDashboardView.vue'),
      meta: { title: '市场情报看板' },
    },
    {
      path: '/market/jobs',
      name: 'market-jobs',
      component: () => import('@/views/MarketJobsView.vue'),
      meta: { title: '市场岗位库' },
    },
    {
      path: '/market/predict',
      name: 'market-predict',
      component: () => import('@/views/MarketPredictView.vue'),
      meta: { title: '薪资预测' },
    },
    { path: '/settings', name: 'settings', component: () => import('@/views/SettingsView.vue'), meta: { title: '设置' } },
  ],
})

export default router
