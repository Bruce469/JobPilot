// 市场情报纯函数：查询参数序列化 / B 后端 {detail} 错误体归一化 / P2 协同的请求体构造
// 不依赖 http 实例（node 环境无 sessionStorage），便于 vitest 单测
import type { AxiosResponseTransformer } from 'axios'
import type { JobPayload } from '@/api/jobs'
import type { MarketJob, PredictRequest } from '@/types/market'

export type MarketQueryValue = string | number | null | undefined

/** 构造查询参数：过滤空串 / null / undefined，与 B 后端可选参数语义一致 */
export function buildMarketQuery(params: object): Record<string, string> {
  const q: Record<string, string> = {}
  for (const [k, v] of Object.entries(params)) {
    if (v !== '' && v != null) q[k] = String(v)
  }
  return q
}

/**
 * B 后端错误体为 { detail: string }，A 的 http.ts 只认 { error: { message } }。
 * 在 axios transformResponse 阶段（早于 http.ts 错误拦截器）把 detail 归一化为 error.message。
 */
export function normalizeMarketBody(body: unknown, status?: number): unknown {
  let data: unknown = body
  if (typeof data === 'string') {
    try {
      data = JSON.parse(data)
    } catch {
      // 非 JSON 响应原样返回
    }
  }
  if (status && status >= 400 && data && typeof data === 'object' && !Array.isArray(data)) {
    const obj = data as { detail?: unknown; error?: unknown }
    if (typeof obj.detail === 'string' && obj.error === undefined) {
      obj.error = { message: obj.detail, code: 'MARKET_ERROR', details: undefined }
    }
  }
  return data
}

/** 适配 axios transformResponse 签名 */
export const normalizeMarketResponse: AxiosResponseTransformer = (data, _headers, status) => {
  return normalizeMarketBody(data, status)
}

// ---------------- P2 协同：表单薪资预测请求 / 市场岗位导入请求 ----------------

/** 预测模型支持的岗位类别白名单（超出归「数据分析」默认） */
const MARKET_CATEGORIES = ['数据分析', '数据科学', '大数据', '算法', 'BI数仓']
const MARKET_JOB_TYPES = ['校招', '社招', '实习']
const MARKET_DEGREES = ['本科', '硕士', '博士']

export interface PredictFormFields {
  position: string
  city: string
  degree: string | null | undefined
  job_type: string | null | undefined
  industry: string | null | undefined
}

/**
 * P2a：岗位表单已填字段 → POST /api/market/predict 请求体。
 * job_category 取表单 industry，五类白名单直传、其他归「数据分析」默认；
 * 学历不在 本科/硕士/博士 传「不限」，岗位类型不在 校招/社招/实习 传「社招」。
 */
export function buildPredictRequest(fields: PredictFormFields): PredictRequest {
  const industry = (fields.industry || '').trim()
  return {
    job_title: fields.position.trim() || '未命名岗位',
    city: fields.city.trim() || '北京',
    job_category: MARKET_CATEGORIES.includes(industry) ? industry : '数据分析',
    education_req: fields.degree && MARKET_DEGREES.includes(fields.degree) ? fields.degree : '不限',
    experience_req: '1-3年',
    job_type: fields.job_type && MARKET_JOB_TYPES.includes(fields.job_type) ? fields.job_type : '社招',
    industry: industry || '其他',
    skills: [],
  }
}

/** 市场脏值（空串 / 'nan' / '不限'）归 null，避免脏值写入 A 库 */
function blankOrNaToNull(v: string | null | undefined): string | null {
  const s = String(v ?? '').trim()
  return s === '' || s.toLowerCase() === 'nan' || s === '不限' ? null : s
}

/** 数据源（B 侧 source id）→ A 侧投递渠道映射 */
export function marketChannelOf(source: string): string | null {
  const map: Record<string, string> = {
    backup: '其他',
    job51: '其他',
    iguopin: '官网',
    nowcoder: '牛客',
  }
  return map[source] ?? null
}

/** P2b：市场岗位 → A 岗位创建请求体（company 为空/ 'nan' 由调用方先拦截校验） */
export function buildMarketJobPayload(row: MarketJob): JobPayload {
  return {
    company: blankOrNaToNull(row.company) ?? '',
    position: blankOrNaToNull(row.title),
    city: blankOrNaToNull(row.city),
    industry: blankOrNaToNull(row.industry),
    job_type: blankOrNaToNull(row.type),
    degree: blankOrNaToNull(row.education),
    channel: marketChannelOf(row.source),
    job_url: row.url || null,
    source_job_id: row.job_id || null,
    publish_date: row.post_date || null,
  }
}
