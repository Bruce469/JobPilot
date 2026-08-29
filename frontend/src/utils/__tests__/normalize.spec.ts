import { describe, expect, it } from 'vitest'
import {
  ACTIVE_STATUSES,
  FAIL_STAGES,
  INTERVIEW_STATUSES,
  STATUS_ALL,
  TERMINAL_STATUSES,
  arrangeOverdueOf,
  defaultFailStage,
  isActive,
  isTerminal,
  overdueEventOf,
  statusMeta,
} from '../normalize'
import type { JobEvent } from '@/types'

describe('状态常量', () => {
  it('状态全集与后端一致（9 个，不含已合并的「简历筛选」）', () => {
    expect(STATUS_ALL).toEqual([
      '待投递',
      '已投递',
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
    expect(ACTIVE_STATUSES).toHaveLength(6)
    expect(ACTIVE_STATUSES).toEqual(['待投递', '已投递', '笔试', '一面', '二面', '三面/HR面'])
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
  it('FAIL_STAGES 与后端一致', () => {
    expect(FAIL_STAGES).toEqual(['简历挂', '笔试挂', '一面挂', '二面挂', '三面挂', 'HR挂', '其他'])
  })
})

describe('defaultFailStage（未通过环节默认值）', () => {
  it('待投递/已投递 → 简历挂', () => {
    expect(defaultFailStage('待投递')).toBe('简历挂')
    expect(defaultFailStage('已投递')).toBe('简历挂')
  })
  it('笔试/一面/二面/三面HR面 → 对应环节', () => {
    expect(defaultFailStage('笔试')).toBe('笔试挂')
    expect(defaultFailStage('一面')).toBe('一面挂')
    expect(defaultFailStage('二面')).toBe('二面挂')
    expect(defaultFailStage('三面/HR面')).toBe('HR挂')
  })
  it('其它/未知 → 其他', () => {
    expect(defaultFailStage('已Offer')).toBe('其他')
    expect(defaultFailStage('')).toBe('其他')
    expect(defaultFailStage('未知状态')).toBe('其他')
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

describe('arrangeOverdueOf（等待环节安排时间）', () => {
  it('等待态且有 next_time 且已过期 → 返回文本并标记 overdue', () => {
    const res = arrangeOverdueOf({ status: '一面', next_time: isoPastMinutes(30) })
    expect(res).not.toBeNull()
    expect(res?.overdue).toBe(true)
    expect(res?.text).toMatch(/^\d{2}-\d{2} \d{2}:\d{2}$/)
  })

  it('等待态且有 next_time 但未到 → 返回文本且不过期', () => {
    const future = new Date(Date.now() + 24 * 3600 * 1000)
    const p = (n: number) => (n < 10 ? `0${n}` : `${n}`)
    const time = `${future.getFullYear()}-${p(future.getMonth() + 1)}-${p(future.getDate())}T${p(future.getHours())}:${p(future.getMinutes())}`
    const res = arrangeOverdueOf({ status: '笔试', next_time: time })
    expect(res).not.toBeNull()
    expect(res?.overdue).toBe(false)
  })

  it('仅日期无时刻的 next_time 也能展示', () => {
    const res = arrangeOverdueOf({ status: '二面', next_time: '2026-09-02' })
    expect(res).not.toBeNull()
    expect(res?.text).toMatch(/^\d{2}-\d{2}$/)
  })

  it('非等待态 → 返回 null（即使有 next_time）', () => {
    expect(arrangeOverdueOf({ status: '已投递', next_time: isoPastMinutes(30) })).toBeNull()
    expect(arrangeOverdueOf({ status: '已拒绝', next_time: isoPastMinutes(30) })).toBeNull()
  })

  it('无 next_time → 返回 null', () => {
    expect(arrangeOverdueOf({ status: '一面', next_time: null })).toBeNull()
  })
})
