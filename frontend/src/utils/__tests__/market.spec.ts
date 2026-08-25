import { describe, expect, it } from 'vitest'
import {
  buildMarketJobPayload,
  buildMarketQuery,
  buildPredictRequest,
  marketChannelOf,
  normalizeMarketBody,
} from '../market'
import type { MarketJob } from '@/types/market'

describe('buildMarketQuery（市场接口查询参数序列化）', () => {
  it('过滤空串 / null / undefined', () => {
    expect(buildMarketQuery({ city: '北京', category: '', source: null, page: undefined })).toEqual({
      city: '北京',
    })
  })

  it('数字参数转字符串并保留 0', () => {
    expect(buildMarketQuery({ page: 1, page_size: 20, offset: 0 })).toEqual({
      page: '1',
      page_size: '20',
      offset: '0',
    })
  })

  it('空对象返回空对象', () => {
    expect(buildMarketQuery({})).toEqual({})
  })
})

describe('normalizeMarketBody（B 后端 {detail} 错误体归一化为 A 的 {error} 结构）', () => {
  it('4xx 且 body 含 detail → 补 error.message', () => {
    const body = normalizeMarketBody({ detail: '模型文件不存在' }, 404) as Record<string, { message: string }>
    expect(body.error?.message).toBe('模型文件不存在')
  })

  it('5xx 同样归一化', () => {
    const body = normalizeMarketBody({ detail: 'DB 不可用' }, 500) as Record<string, { message: string }>
    expect(body.error?.message).toBe('DB 不可用')
  })

  it('成功响应（status < 400）不改写', () => {
    const body = normalizeMarketBody({ detail: '普通字段' }, 200) as Record<string, unknown>
    expect(body.error).toBeUndefined()
  })

  it('已是 A 错误结构的不覆盖', () => {
    const body = normalizeMarketBody({ error: { message: '原有错误' } }, 500) as Record<string, { message: string }>
    expect(body.error?.message).toBe('原有错误')
  })

  it('字符串 JSON 先解析再归一化', () => {
    const body = normalizeMarketBody('{"detail":"找不到接口"}', 404) as Record<string, { message: string }>
    expect(body.error?.message).toBe('找不到接口')
  })

  it('非 JSON 字符串原样返回', () => {
    expect(normalizeMarketBody('<html>err</html>', 500)).toBe('<html>err</html>')
  })
})

describe('buildPredictRequest（岗位表单 → 薪资预测请求体）', () => {
  it('五类岗位行业直传 job_category，其他归「数据分析」默认', () => {
    expect(buildPredictRequest({ position: '数据工程师', city: '上海', degree: null, job_type: null, industry: '算法' }).job_category).toBe('算法')
    expect(buildPredictRequest({ position: '产品经理', city: '北京', degree: null, job_type: null, industry: '互联网' }).job_category).toBe('数据分析')
    expect(buildPredictRequest({ position: '数据工程师', city: '北京', degree: null, job_type: null, industry: null }).job_category).toBe('数据分析')
  })

  it('学历白名单直传、其他值归「不限」', () => {
    expect(buildPredictRequest({ position: 'x', city: '北京', degree: '硕士', job_type: null, industry: null }).education_req).toBe('硕士')
    expect(buildPredictRequest({ position: 'x', city: '北京', degree: '不限', job_type: null, industry: null }).education_req).toBe('不限')
    expect(buildPredictRequest({ position: 'x', city: '北京', degree: null, job_type: null, industry: null }).education_req).toBe('不限')
  })

  it('岗位类型白名单直传、其他值归「社招」，经验默认 1-3年', () => {
    const req = buildPredictRequest({ position: 'x', city: '北京', degree: null, job_type: '实习', industry: null })
    expect(req.job_type).toBe('实习')
    expect(buildPredictRequest({ position: 'x', city: '北京', degree: null, job_type: null, industry: null }).job_type).toBe('社招')
    expect(req.experience_req).toBe('1-3年')
    expect(req.skills).toEqual([])
  })

  it('城市为空默认北京，industry 空默认其他', () => {
    const req = buildPredictRequest({ position: 'x', city: '', degree: null, job_type: null, industry: '' })
    expect(req.city).toBe('北京')
    expect(req.industry).toBe('其他')
    expect(req.job_title).toBe('x')
  })
})

function makeMarketJob(overrides: Partial<MarketJob>): MarketJob {
  return {
    job_id: 'job_1',
    title: '数据分析师',
    category: '数据分析',
    type: '社招',
    company: '某某科技',
    industry: '互联网',
    company_size: null,
    city: '北京',
    salary_raw: '20k-30k',
    salary_min: 20000,
    salary_max: 30000,
    salary_avg: 25000,
    experience: '1-3年',
    education: '本科',
    tags: [],
    post_date: '2026-01-01',
    crawl_date: '2026-01-02',
    url: 'https://example.com/job/1',
    source: 'nowcoder',
    skills: [],
    skills_count: 0,
    ...overrides,
  }
}

describe('buildMarketJobPayload（市场岗位 → A 岗位创建请求体）', () => {
  it('字段映射正确（title→position、url→job_url、job_id→source_job_id、post_date→publish_date）', () => {
    const p = buildMarketJobPayload(makeMarketJob({}))
    expect(p).toMatchObject({
      company: '某某科技',
      position: '数据分析师',
      city: '北京',
      industry: '互联网',
      job_type: '社招',
      degree: '本科',
      job_url: 'https://example.com/job/1',
      source_job_id: 'job_1',
      publish_date: '2026-01-01',
    })
  })

  it('脏值 nan / 不限 / 空串 归 null', () => {
    const p = buildMarketJobPayload(
      makeMarketJob({ company: 'nan', industry: 'nan', city: 'nan', type: '不限', education: '不限', url: '', post_date: '' }),
    )
    expect(p.company).toBe('')
    expect(p.industry).toBeNull()
    expect(p.city).toBeNull()
    expect(p.job_type).toBeNull()
    expect(p.degree).toBeNull()
    expect(p.job_url).toBeNull()
    expect(p.publish_date).toBeNull()
  })
})

describe('marketChannelOf（数据源 → 投递渠道）', () => {
  it('backup/job51 → 其他，iguopin → 官网，nowcoder → 牛客，未知源 → null', () => {
    expect(marketChannelOf('backup')).toBe('其他')
    expect(marketChannelOf('job51')).toBe('其他')
    expect(marketChannelOf('iguopin')).toBe('官网')
    expect(marketChannelOf('nowcoder')).toBe('牛客')
    expect(marketChannelOf('unknown')).toBeNull()
  })
})
