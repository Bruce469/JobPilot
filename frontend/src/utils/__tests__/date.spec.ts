import { describe, expect, it } from 'vitest'
import {
  deadlineLabel,
  daysUntil,
  eventInRange,
  formatDate,
  formatDateTime,
  isOverdue,
  isThisWeek,
  isToday,
  isWithinDays,
  parseDate,
  toISODate,
} from '../date'

function isoAddDays(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return toISODate(d)
}

describe('parseDate / format', () => {
  it('解析 YYYY-MM-DD', () => {
    const d = parseDate('2026-08-24')
    expect(d?.getFullYear()).toBe(2026)
    expect(d?.getMonth()).toBe(7)
    expect(d?.getDate()).toBe(24)
  })

  it('解析 datetime 文本', () => {
    const d = parseDate('2026-08-24T10:30:00')
    expect(d?.getDate()).toBe(24)
  })

  it('非法输入返回 null', () => {
    expect(parseDate('')).toBeNull()
    expect(parseDate(null)).toBeNull()
    expect(parseDate('abc')).toBeNull()
  })

  it('formatDate 只取日期部分', () => {
    expect(formatDate('2026-08-24T10:30:00')).toBe('2026-08-24')
    expect(formatDate('2026-08-24')).toBe('2026-08-24')
    expect(formatDate(null)).toBe('')
  })

  it('formatDateTime 展示为 YYYY-MM-DD HH:MM', () => {
    expect(formatDateTime('2026-08-24T09:05:00')).toBe('2026-08-24 09:05')
  })
})

describe('daysUntil / 截止相关', () => {
  it('今天为 0', () => {
    expect(daysUntil(isoAddDays(0))).toBe(0)
  })
  it('未来为正', () => {
    expect(daysUntil(isoAddDays(2))).toBe(2)
  })
  it('过去为负', () => {
    expect(daysUntil(isoAddDays(-1))).toBe(-1)
  })
  it('非法为 null', () => {
    expect(daysUntil(null)).toBeNull()
  })
  it('isWithinDays(≤3)', () => {
    expect(isWithinDays(isoAddDays(3), 3)).toBe(true)
    expect(isWithinDays(isoAddDays(4), 3)).toBe(false)
    expect(isWithinDays(isoAddDays(-1), 3)).toBe(false)
  })
  it('isOverdue', () => {
    expect(isOverdue(isoAddDays(-1))).toBe(true)
    expect(isOverdue(isoAddDays(1))).toBe(false)
  })
  it('isToday', () => {
    expect(isToday(isoAddDays(0))).toBe(true)
    expect(isToday(isoAddDays(1))).toBe(false)
  })
  it('isThisWeek 覆盖今天与未来 7 天', () => {
    expect(isThisWeek(isoAddDays(0))).toBe(true)
    expect(isThisWeek(isoAddDays(6))).toBe(true)
    expect(isThisWeek(isoAddDays(-1))).toBe(false)
  })
})

describe('deadlineLabel', () => {
  it('紧急 ≤3 天', () => {
    expect(deadlineLabel(isoAddDays(3)).kind).toBe('urgent')
  })
  it('已过为 overdue', () => {
    const l = deadlineLabel(isoAddDays(-2))
    expect(l.kind).toBe('overdue')
    expect(l.text).toContain('已过')
  })
  it('正常', () => {
    expect(deadlineLabel(isoAddDays(10)).kind).toBe('normal')
  })
  it('无截止返回空', () => {
    expect(deadlineLabel(null)).toEqual({ text: '', kind: '' })
  })
})

describe('eventInRange', () => {
  it('今日事件（range 0）', () => {
    expect(eventInRange(isoAddDays(0), 0)).toBe(true)
    expect(eventInRange(isoAddDays(1), 0)).toBe(false)
  })
  it('本周事件（range 7）', () => {
    expect(eventInRange(isoAddDays(5), 7)).toBe(true)
    expect(eventInRange(isoAddDays(8), 7)).toBe(false)
    expect(eventInRange(null, 7)).toBe(false)
  })
})
