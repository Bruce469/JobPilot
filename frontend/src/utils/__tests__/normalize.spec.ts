import { describe, expect, it } from 'vitest'
import {
  ACTIVE_STATUSES,
  INTERVIEW_STATUSES,
  STATUS_ALL,
  TERMINAL_STATUSES,
  isActive,
  isTerminal,
  overdueEventOf,
  statusMeta,
} from '../normalize'
import type { JobEvent } from '@/types'

describe('状态常量', () => {
  it('状态全集与后端一致（10 个）', () => {
    expect(STATUS_ALL).toEqual([
      '待投递',
      '已投递',
      '简历筛选',
      '笔试',
      '一面',
      '二面',
      '三面/HR面',
      '已Offer',
      '已拒绝',
      '已放弃',
    ])
  })
  it('终态与进行中状态划分正确', () => {
    expect(TERMINAL_STATUSES).toEqual(['已Offer', '已拒绝', '已放弃'])
    expect(ACTIVE_STATUSES).toHaveLength(7)
    expect(isTerminal('已Offer')).toBe(true)
    expect(isTerminal('已拒绝')).toBe(true)
    expect(isTerminal('已投递')).toBe(false)
    expect(isActive('二面')).toBe(true)
    expect(isActive('已放弃')).toBe(false)
  })
  it('面试/笔试状态集合', () => {
    expect(INTERVIEW_STATUSES.has('笔试')).toBe(true)
    expect(INTERVIEW_STATUSES.has('一面')).toBe(true)
    expect(INTERVIEW_STATUSES.has('三面/HR面')).toBe(true)
    expect(INTERVIEW_STATUSES.has('已投递')).toBe(false)
  })
  it('statusMeta 始终有兜底', () => {
    expect(statusMeta('已Offer').color).toBeTruthy()
    expect(statusMeta('未知状态').color).toBeTruthy()
  })
})

function makeEvent(overrides: Partial<JobEvent>): JobEvent {
  return {
    id: 'e1',
    job_id: 'j1',
    time: '2026-01-01T00:00:00',
    type: '状态流转',
    from_status: '已投递',
    to_status: '笔试',
    note: null,
    created_at: '2026-01-01T00:00:00',
    ...overrides,
  }
}

function isoPastMinutes(minutes: number): string {
  const d = new Date(Date.now() - minutes * 60 * 1000)
  const p = (n: number) => (n < 10 ? `0${n}` : `${n}`)
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:00`
}

describe('overdueEventOf（过期笔试/面试事件）', () => {
  it('岗位处于面试状态且事件时间已过 → 返回该事件', () => {
    const ev = makeEvent({ time: isoPastMinutes(60), to_status: '笔试' })
    const job = { status: '笔试' }
    const res = overdueEventOf(job, [ev])
    expect(res).not.toBeNull()
    expect(res?.to_status).toBe('笔试')
  })

  it('事件时间未到 → 不标红', () => {
    const future = new Date(Date.now() + 60 * 60 * 1000)
    const p = (n: number) => (n < 10 ? `0${n}` : `${n}`)
    const time = `${future.getFullYear()}-${p(future.getMonth() + 1)}-${p(future.getDate())}T${p(future.getHours())}:${p(future.getMinutes())}:00`
    const ev = makeEvent({ time, to_status: '一面' })
    expect(overdueEventOf({ status: '一面' }, [ev])).toBeNull()
  })

  it('非面试/笔试状态 → 不标红', () => {
    const ev = makeEvent({ time: isoPastMinutes(60), to_status: '已投递' })
    expect(overdueEventOf({ status: '已投递' }, [ev])).toBeNull()
  })

  it('已推进到下一状态 → 不标红', () => {
    const ev = makeEvent({ time: isoPastMinutes(60), to_status: '笔试' })
    expect(overdueEventOf({ status: '一面' }, [ev])).toBeNull()
  })
})
