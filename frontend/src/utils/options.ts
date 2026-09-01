// 筛选候选池合并：静态候选在前 + DB distinct 值在后，保序去重。
// 城市/行业多选弹窗共用；DB 值即使不在静态常量中也必须保留（覆盖库中已存在值）。
import { filterRecent, unique } from './recent'

export function mergeCandidates(staticValues: string[], dbValues: string[]): string[] {
  return [...new Set([...staticValues, ...dbValues])]
}

/**
 * 下拉选项顺序：最近点击值（已按候选池过滤、时间倒序）置顶，随后补全完整候选池其余值，整体去重。
 * 只对仍属于候选池的最近值生效——失效值由 filterRecent 过滤，不会出现已下线的选项。
 */
export function withRecentOnTop(recent: string[], pool: string[]): string[] {
  return unique([...filterRecent(recent, pool), ...pool])
}

