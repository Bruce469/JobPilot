// 最近选择记录工具：localStorage 存取，带 try/catch 容错与可注入 storage（便于无 jsdom 环境下单测）
export const RECENT_CITY_KEY = 'job_tracker_recent_cities' // 城市最近选择，容量 5
export const RECENT_NATURE_KEY = 'job_tracker_recent_natures' // 性质最近选择，容量 10

/** 最小 storage 接口（localStorage 子集），测试可注入内存实现 */
export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

let defaultStorageImpl: StorageLike | null | undefined

/** 取浏览器 localStorage；不可用（隐私模式/SSR/测试环境）返回 null，调用方按空处理 */
function getDefaultStorage(): StorageLike | null {
  if (defaultStorageImpl !== undefined) return defaultStorageImpl
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      defaultStorageImpl = window.localStorage
    } else {
      defaultStorageImpl = null
    }
  } catch {
    defaultStorageImpl = null
  }
  return defaultStorageImpl
}

/**
 * 读取最近选择列表。损坏 JSON / 非数组 / 数组内非字符串项都会被丢弃，返回纯字符串数组。
 * 读取方负责按当前候选池过滤失效值（filterRecent）。
 */
export function readRecent(key: string, storage?: StorageLike): string[] {
  const s = storage ?? getDefaultStorage()
  if (!s) return []
  try {
    const raw = s.getItem(key)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((x): x is string => typeof x === 'string')
  } catch {
    return []
  }
}

/**
 * 写入最近选择：value 去重后置顶（unshift），再按 cap 截断。
 * 返回写入后的列表；存储不可用/写入失败（隐私模式、配额超限）时静默降级为读取结果。
 */
export function pushRecent(key: string, value: string, cap = 5, storage?: StorageLike): string[] {
  const s = storage ?? getDefaultStorage()
  const current = readRecent(key, s ?? undefined)
  if (!value) return current
  const next = [value, ...current.filter((v) => v !== value)].slice(0, cap)
  if (s) {
    try {
      s.setItem(key, JSON.stringify(next))
    } catch {
      return readRecent(key, s)
    }
  }
  return next
}

/** 过滤出仍属于候选池的最近值（失效值由读取方清理，不反向写回） */
export function filterRecent(recent: string[], pool: string[]): string[] {
  const set = new Set(pool)
  return recent.filter((v) => set.has(v))
}

/** 保序去重 */
export function unique(items: string[]): string[] {
  return [...new Set(items)]
}
