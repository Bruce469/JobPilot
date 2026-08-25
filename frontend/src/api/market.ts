// 市场情报（JobPulse 合并）API 封装：复用 A 的 http.ts
// （X-Auth-Token 注入 / 401 刷新重试 / 统一错误），接口全部挂 /api/market/ 前缀
import http from './http'
import type { AxiosRequestConfig } from 'axios'
import { buildMarketQuery, normalizeMarketResponse } from '@/utils/market'
import type {
  MarketHealth,
  MarketJobsParams,
  MarketJobsResponse,
  MarketMeta,
  MarketSummaryParams,
  MarketSummaryResponse,
  PredictRequest,
  PredictResponse,
} from '@/types/market'

// B 后端错误体为 { detail }，通过 transformResponse 归一化为 A 的 { error } 结构，
// 这样 http.ts 错误拦截器能正确展示 detail 文案（详见 utils/market.ts）
function get<T>(url: string, config: AxiosRequestConfig = {}): Promise<T> {
  return http
    .get<T>(url, { ...config, transformResponse: [normalizeMarketResponse] })
    .then((r) => r.data)
}

function post<T>(url: string, payload: unknown): Promise<T> {
  return http
    .post<T>(url, payload, { transformResponse: [normalizeMarketResponse] })
    .then((r) => r.data)
}

export function getMarketHealth(): Promise<MarketHealth> {
  return get<MarketHealth>('/market/health')
}

export function getMarketSummary(params: MarketSummaryParams = {}): Promise<MarketSummaryResponse> {
  return get<MarketSummaryResponse>('/market/jobs/summary', { params: buildMarketQuery(params) })
}

export function getMarketJobs(params: MarketJobsParams = {}): Promise<MarketJobsResponse> {
  return get<MarketJobsResponse>('/market/jobs', { params: buildMarketQuery(params) })
}

export function getMarketMeta(): Promise<MarketMeta> {
  return get<MarketMeta>('/market/meta')
}

export function predictSalary(payload: PredictRequest): Promise<PredictResponse> {
  return post<PredictResponse>('/market/predict', payload)
}
