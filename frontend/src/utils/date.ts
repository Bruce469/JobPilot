// 日期工具：全部为纯函数，便于单测
function pad(n: number): string {
  return n < 10 ? `0${n}` : `${n}`
}

export function toISODate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function todayStr(): string {
  return toISODate(new Date())
}

/** 解析 YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS（本地时间，无时区偏移） */
export function parseDate(s: string | null | undefined): Date | null {
  if (!s) return null
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!m) return null
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  return Number.isNaN(d.getTime()) ? null : d
}

/** 解析完整 datetime（含时刻），用于过期事件等需要精确时刻比较的场景 */
export function parseDateTime(s: string | null | undefined): Date | null {
  if (!s) return null
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/)
  if (m) {
    const d = new Date(
      Number(m[1]),
      Number(m[2]) - 1,
      Number(m[3]),
      Number(m[4]),
      Number(m[5]),
      Number(m[6] || 0),
    )
    return Number.isNaN(d.getTime()) ? null : d
  }
  return parseDate(s)
}

/** 取日期部分 YYYY-MM-DD */
export function formatDate(s: string | null | undefined): string {
  if (!s) return ''
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})/)
  return m ? `${m[1]}-${m[2]}-${m[3]}` : String(s)
}

/** 格式化为 YYYY-MM-DD HH:MM */
export function formatDateTime(s: string | null | undefined): string {
  if (!s) return ''
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/)
  if (m) return `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}`
  return formatDate(s)
}

function startOfToday(): Date {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d
}

/** 距今天的天数（含今天=0，未来为正，过去为负），解析失败返回 null */
export function daysUntil(s: string | null | undefined): number | null {
  const d = parseDate(s)
  if (!d) return null
  const target = new Date(d)
  target.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - startOfToday().getTime()) / 86400000)
}

export function isWithinDays(s: string | null | undefined, n: number): boolean {
  const d = daysUntil(s)
  return d !== null && d >= 0 && d <= n
}

export function isOverdue(s: string | null | undefined): boolean {
  const d = daysUntil(s)
  return d !== null && d < 0
}

export function isToday(s: string | null | undefined): boolean {
  return daysUntil(s) === 0
}

/** 是否为今天到未来 7 天（含边界）之内 */
export function isThisWeek(s: string | null | undefined): boolean {
  const d = parseDate(s)
  if (!d) return false
  const today = startOfToday()
  const end = new Date(today)
  end.setDate(end.getDate() + 7)
  const target = new Date(d)
  target.setHours(0, 0, 0, 0)
  return target >= today && target < end
}

export interface DeadlineLabel {
  text: string
  kind: 'overdue' | 'urgent' | 'normal' | ''
}

/** 截止日期的展示文案与紧急程度（≤3 天为 urgent，已过为 overdue） */
export function deadlineLabel(s: string | null | undefined): DeadlineLabel {
  const d = daysUntil(s)
  if (d === null) return { text: '', kind: '' }
  if (d < 0) return { text: `已过 ${-d} 天`, kind: 'overdue' }
  if (d === 0) return { text: '今天截止', kind: 'urgent' }
  if (d <= 3) return { text: `${d} 天后截止`, kind: 'urgent' }
  return { text: `${d} 天后`, kind: 'normal' }
}

/** 今日/本周安排用：事件时间是否在今天（days=0）或未来 N 天内 */
export function eventInRange(time: string | null | undefined, rangeDays: number): boolean {
  const d = daysUntil(time)
  return d !== null && d >= 0 && d <= rangeDays
}
