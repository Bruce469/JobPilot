import { describe, expect, it } from 'vitest'
import type { StorageLike } from '../recent'
import { RECENT_CITY_KEY, filterRecent, pushRecent, readRecent, unique } from '../recent'

/** 内存版 storage：模拟 localStorage，可预置原始字符串（含损坏数据） */
function createMockStorage(init?: Record<string, string>): StorageLike {
  const data = new Map<string, string>(Object.entries(init ?? {}))
  return {
    getItem: (k) => (data.has(k) ? (data.get(k) as string) : null),
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
  }
}

describe('pushRecent', () => {
  it('新值置顶（最近在前）', () => {
    const s = createMockStorage()
    pushRecent(RECENT_CITY_KEY, '北京', 5, s)
    pushRecent(RECENT_CITY_KEY, '上海', 5, s)
    expect(readRecent(RECENT_CITY_KEY, s)).toEqual(['上海', '北京'])
  })

  it('重复值去重并置顶', () => {
    const s = createMockStorage({ [RECENT_CITY_KEY]: JSON.stringify(['上海', '北京']) })
    pushRecent(RECENT_CITY_KEY, '北京', 5, s)
    expect(readRecent(RECENT_CITY_KEY, s)).toEqual(['北京', '上海'])
  })

  it('按 cap 截断', () => {
    const s = createMockStorage({ [RECENT_CITY_KEY]: JSON.stringify(['上海', '北京']) })
    const result = pushRecent(RECENT_CITY_KEY, '深圳', 2, s)
    expect(result).toEqual(['深圳', '上海'])
    expect(readRecent(RECENT_CITY_KEY, s)).toEqual(['深圳', '上海'])
  })

  it('无注入 storage 时静默降级（node 环境无 localStorage）', () => {
    const result = pushRecent(RECENT_CITY_KEY, '北京', 5)
    expect(Array.isArray(result)).toBe(true)
  })
})

describe('readRecent', () => {
  it('无数据返回空数组', () => {
    expect(readRecent(RECENT_CITY_KEY, createMockStorage())).toEqual([])
  })

  it('损坏 JSON 按空处理', () => {
    const s = createMockStorage({ [RECENT_CITY_KEY]: '{not-json' })
    expect(readRecent(RECENT_CITY_KEY, s)).toEqual([])
  })

  it('非数组按空处理', () => {
    const s = createMockStorage({ [RECENT_CITY_KEY]: '{"a":1}' })
    expect(readRecent(RECENT_CITY_KEY, s)).toEqual([])
  })

  it('过滤数组中的非字符串项', () => {
    const s = createMockStorage({ [RECENT_CITY_KEY]: JSON.stringify(['北京', 123, null]) })
    expect(readRecent(RECENT_CITY_KEY, s)).toEqual(['北京'])
  })
})

describe('filterRecent', () => {
  it('过滤候选池外的失效值', () => {
    expect(filterRecent(['北京', '深圳', '已下线'], ['北京', '上海', '深圳'])).toEqual(['北京', '深圳'])
  })
})

describe('unique', () => {
  it('保序去重', () => {
    expect(unique(['北京', '上海', '北京', '深圳'])).toEqual(['北京', '上海', '深圳'])
  })
})
