// 市场情报（JobPulse 合并）类型定义：字段对齐 B 后端 _serialize_job 与 stats 模块输出
// （参考 jobpulse_key/src_api_app.py、src_api_stats.py，P0 合并后端统一挂 /api/market/ 前缀）

/** GET /api/market/jobs 单条岗位（B 后端 _serialize_job 输出） */
export interface MarketJob {
  job_id: string
  title: string
  category: string
  type: string
  company: string
  industry: string
  company_size: string | null
  city: string
  salary_raw: string | null
  salary_min: number | null
  salary_max: number | null
  salary_avg: number | null
  experience: string
  education: string
  tags: string[]
  post_date: string | null
  crawl_date: string | null
  url: string
  source: string
  skills: string[]
  skills_count: number
}

/** 全量概览（build_dashboard_data 的 summary 输出） */
export interface MarketSummary {
  total: number
  mean_salary: number
  median_salary: number
  cities: string[]
  categories: string[]
  educations: string[]
  generated_at: string
}

/** 筛选后概览（stats 模块 stats() 输出） */
export interface MarketFiltered {
  total: number
  mean_salary: number
  median_salary: number
}

export interface MarketSalaryHist {
  bins: number[]
  counts: number[]
  step: number
}

export interface MarketCitySalary {
  cities: string[]
  medians: number[]
}

export interface MarketSkillTopItem {
  name: string
  count: number
  ratio: number
}

export interface MarketCategoryDistItem {
  name: string
  value: number
}

export interface MarketHeatmap {
  /** x 为岗位类别，y 为城市，data 为 [j=类别下标, i=城市下标, count] */
  x: string[]
  y: string[]
  data: [number, number, number][]
}

/** GET /api/market/jobs/summary 的 charts 字段（stats 模块 build_charts 输出） */
export interface MarketCharts {
  salary_hist: MarketSalaryHist
  city_salary: MarketCitySalary
  skill_top: MarketSkillTopItem[]
  category_dist: MarketCategoryDistItem[]
  heatmap: MarketHeatmap
}

export interface MarketSummaryResponse {
  summary: MarketSummary
  filtered: MarketFiltered
  charts: MarketCharts
  sources: string[]
}

/** GET /api/market/meta：筛选选项（summary 全字段 + sources） */
export interface MarketMeta extends MarketSummary {
  sources: string[]
}

export interface MarketJobsResponse {
  total: number
  page: number
  page_size: number
  total_pages: number
  items: MarketJob[]
}

/** 岗位列表排序字段（与 B 后端 Query sort_by 一一对应） */
export type MarketSortBy = 'crawl_date' | 'post_date' | 'salary_avg'

export interface MarketSummaryParams {
  city?: string
  category?: string
  education?: string
  source?: string
}

export interface MarketJobsParams extends MarketSummaryParams {
  experience?: string
  job_type?: string
  keyword?: string
  page?: number
  page_size?: number
  sort_by?: MarketSortBy
  order?: 'asc' | 'desc'
}

/** GET /api/market/health */
export interface MarketHealth {
  status: string
  jobs: number
  snapshots: number
  db: string
}

/** POST /api/market/predict 请求（对应 B 后端 PredictRequest） */
export interface PredictRequest {
  job_title: string
  city: string
  job_category: string
  education_req: string
  experience_req: string
  job_type: string
  industry: string
  company_size?: string | null
  skills: string[]
}

export interface PredictResponse {
  predicted_salary_avg: number
  salary_band: string
  note: string
}
