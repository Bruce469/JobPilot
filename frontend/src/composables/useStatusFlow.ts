// 状态流转共用逻辑：看板卡片下拉 / 列表行内下拉 / 拖拽流转统一走此流程
import { ElMessage, ElMessageBox } from 'element-plus'
import { useJobsStore } from '@/stores/jobs'

/**
 * 弹出备注输入并执行状态流转。
 * 返回 true 表示流转成功，false 表示用户取消或失败（已弹出错误提示）。
 */
export function useStatusFlow() {
  const jobsStore = useJobsStore()

  async function flowStatus(id: string, status: string): Promise<boolean> {
    let note: string | undefined
    try {
      const r = await ElMessageBox.prompt(
        `将岗位状态流转为「${status}」，可填写备注（可选）。`,
        '状态流转',
        {
          confirmButtonText: '流转',
          cancelButtonText: '取消',
          inputPlaceholder: '如：收到笔试邀请 / 一面约在 2026-09-02',
          inputType: 'textarea',
          inputValue: '',
        },
      )
      note = (r.value as string)?.trim() || undefined
    } catch {
      return false // 用户取消
    }
    try {
      await jobsStore.changeStatus(id, status, note)
      ElMessage.success(`已流转至「${status}」`)
      return true
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : '状态流转失败')
      return false
    }
  }

  return { flowStatus }
}
