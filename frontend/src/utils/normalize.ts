// 状态常量与展示元数据（对应 backend/app/dao.py STATUS_ALL / TERMINAL）
import type { Job, JobEvent } from '@/types'
import { parseDateTime } from './date'

export const STATUS_ALL = [
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
] as const

export type JobStatus = (typeof STATUS_ALL)[number]

export const ACTIVE_STATUSES: readonly string[] = STATUS_ALL.slice(0, 7)
export const TERMINAL_STATUSES: readonly string[] = ['已Offer', '已拒绝', '已放弃']

/** 面试/笔试类状态：用于过期事件提醒 */
export const INTERVIEW_STATUSES = new Set(['笔试', '一面', '二面', '三面/HR面'])

export function isTerminal(status: string): boolean {
  return TERMINAL_STATUSES.includes(status)
}

export function isActive(status: string): boolean {
  return ACTIVE_STATUSES.includes(status)
}

export const JOB_TYPES = ['校招', '社招', '实习']
export const DEGREES = ['本科', '硕士', '博士']
export const CHANNELS = ['官网', 'Boss直聘', '牛客', '内推', '邮箱', '其他']
export const INDUSTRIES = ['互联网', '金融', '国企', '外企', '制造业', '其他']
export const PROBE_STATUSES = ['未探测', '成功', '失败', '需人工']

export interface StatusMeta {
  color: string
  bg: string
  border: string
}

export const STATUS_META: Record<string, StatusMeta> = {
  待投递: { color: '#3a6ea5', bg: '#eaf1fa', border: '#c9dcf2' },
  已投递: { color: '#1d5bd7', bg: '#e8f0ff', border: '#c0d6fb' },
  简历筛选: { color: '#0e8a7d', bg: '#e2f5f2', border: '#b5e5de' },
  笔试: { color: '#d97706', bg: '#fdf1dc', border: '#f5dcae' },
  一面: { color: '#7c3aed', bg: '#f1eafd', border: '#d8c8f8' },
  二面: { color: '#7c3aed', bg: '#f1eafd', border: '#d8c8f8' },
  '三面/HR面': { color: '#6d28d9', bg: '#f4eafb', border: '#ddc4f2' },
  已Offer: { color: '#15803d', bg: '#e4f6ea', border: '#b6e4c4' },
  已拒绝: { color: '#dc2626', bg: '#fdecec', border: '#f6c6c6' },
  已放弃: { color: '#6b7280', bg: '#f1f2f4', border: '#d9dade' },
}

export function statusMeta(status: string): StatusMeta {
  return STATUS_META[status] ?? { color: '#6b7280', bg: '#f3f4f6', border: '#d9dade' }
}

/**
 * 过期事件检测（PRD 4.3）：岗位处于笔试/面试类状态，且最后一次流转到该状态的事件时间已过，
 * 说明该笔试/面试时间已过而状态未推进，返回该事件供列表标红提醒。
 */
export function overdueEventOf(job: Pick<Job, 'status'>, events: JobEvent[]): JobEvent | null {
  if (!INTERVIEW_STATUSES.has(job.status)) return null
  const now = new Date()
  for (const ev of events) {
    if (ev.type !== '状态流转') continue
    if (ev.to_status === job.status) {
      const t = parseDateTime(ev.time)
      if (t && t.getTime() < now.getTime()) return ev
    }
  }
  return null
}

/** 列表/看板排序白名单（与后端 SORT_WHITELIST 一致） */
export const SORT_FIELDS = [
  { value: 'updated_at', label: '更新时间' },
  { value: 'created_at', label: '创建时间' },
  { value: 'company', label: '公司名' },
  { value: 'status', label: '状态' },
  { value: 'position', label: '岗位名' },
  { value: 'deadline', label: '截止日期' },
  { value: 'applied_at', label: '投递时间' },
]
