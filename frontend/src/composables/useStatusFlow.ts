// 状态流转共用逻辑：看板卡片下拉 / 列表行内下拉统一走全局弹窗（备注 + 条件字段）；
// 拖拽快速流转不弹窗，由调用方直接调 store.changeStatus。
import { ElMessage } from 'element-plus'
import { useJobsStore } from '@/stores/jobs'
import { requestStatusFlow } from './statusFlowController'

/**
 * 弹出状态流转对话框（备注 + 可选的安排时间/未通过环节）并执行流转。
 * 返回 true 表示流转成功，false 表示用户取消或失败（已弹出错误提示）。
 * fromStatus 用于「已拒绝」时预填未通过环节默认值。
 */
export function useStatusFlow() {
  const jobsStore = useJobsStore()

  async function flowStatus(id: string, status: string, fromStatus: string): Promise<boolean> {
    const r = await requestStatusFlow({ toStatus: status, fromStatus })
    if (!r) return false // 用户取消
    try {
      await jobsStore.changeStatus(id, status, r.note, undefined, r.next_time, r.fail_stage)
      ElMessage.success(`已流转至「${status}」`)
      return true
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : '状态流转失败')
      return false
    }
  }

  return { flowStatus }
}
