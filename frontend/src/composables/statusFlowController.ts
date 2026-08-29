// 状态流转弹窗控制器：模块级单例状态，供 StatusFlowDialog.vue 与 useStatusFlow.ts 协作。
// 调用方 requestStatusFlow 打开全局弹窗并返回 Promise；弹窗确认/取消后 resolve。
import { reactive } from 'vue'
import { defaultFailStage } from '@/utils/normalize'

export interface StatusFlowResult {
  note?: string
  next_time?: string | null
  fail_stage?: string | null
}

interface StatusFlowState {
  visible: boolean
  toStatus: string
  fromStatus: string
  note: string
  nextTime: string | null
  failStage: string
  resolve: ((r: StatusFlowResult | null) => void) | null
}

const state = reactive<StatusFlowState>({
  visible: false,
  toStatus: '',
  fromStatus: '',
  note: '',
  nextTime: null,
  failStage: '',
  resolve: null,
})

/** 打开流转弹窗；用户确认时 resolve 表单结果，取消时 resolve null */
export function requestStatusFlow(opts: { toStatus: string; fromStatus: string }): Promise<StatusFlowResult | null> {
  // 理论上前一次弹窗已关闭（resolve 已清空）；兜底避免遗留 pending
  if (state.resolve) {
    state.resolve(null)
    state.resolve = null
  }
  state.toStatus = opts.toStatus
  state.fromStatus = opts.fromStatus
  state.note = ''
  state.nextTime = null
  state.failStage = defaultFailStage(opts.fromStatus)
  state.visible = true
  return new Promise<StatusFlowResult | null>((resolve) => {
    state.resolve = resolve
  })
}

/** 弹窗确认：汇总表单值（空值以 null 表示未设置） */
export function confirmStatusFlow(): void {
  if (!state.resolve) return
  const r: StatusFlowResult = {}
  const note = state.note.trim()
  if (note) r.note = note
  r.next_time = state.nextTime || null
  r.fail_stage = state.failStage || null
  state.resolve(r)
  state.resolve = null
  state.visible = false
}

/** 弹窗取消 */
export function cancelStatusFlow(): void {
  if (!state.resolve) return
  state.resolve(null)
  state.resolve = null
  state.visible = false
}

export function statusFlowState(): StatusFlowState {
  return state
}
