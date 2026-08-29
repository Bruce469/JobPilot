<script setup lang="ts">
// 全局状态流转单例弹窗：由 statusFlowController 驱动，挂载在 App.vue。
// 备注必填、安排时间与未通过环节为条件字段，按目标状态显示。
import { computed } from 'vue'
import { cancelStatusFlow, confirmStatusFlow, statusFlowState } from '@/composables/statusFlowController'
import { FAIL_STAGES, INTERVIEW_STATUSES } from '@/utils/normalize'

const state = statusFlowState()

const showArrange = computed(() => INTERVIEW_STATUSES.has(state.toStatus))
const showFailStage = computed(() => state.toStatus === '已拒绝')

function onClosed() {
  // 用户通过 ESC / 遮罩关闭时与取消等价
  cancelStatusFlow()
}
</script>

<template>
  <el-dialog
    :model-value="state.visible"
    title="状态流转"
    width="460px"
    append-to-body
    :close-on-click-modal="false"
    @update:model-value="(v: boolean) => { if (!v) cancelStatusFlow() }"
    @closed="onClosed"
  >
    <div class="flow-tip">将岗位状态流转为「{{ state.toStatus }}」</div>

    <div class="flow-form">
      <div class="form-row">
        <div class="form-label">备注</div>
        <el-input
          v-model="state.note"
          type="textarea"
          :rows="3"
          maxlength="500"
          show-word-limit
          placeholder="如：收到笔试邀请 / 一面约在 …"
        />
      </div>

      <div v-if="showArrange" class="form-row">
        <div class="form-label">安排时间</div>
        <el-date-picker
          v-model="state.nextTime"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm"
          placeholder="笔试/面试时间，可留空"
          clearable
          style="width: 100%"
        />
      </div>

      <div v-if="showFailStage" class="form-row">
        <div class="form-label">未通过环节</div>
        <el-select v-model="state.failStage" style="width: 100%">
          <el-option v-for="s in FAIL_STAGES" :key="s" :label="s" :value="s" />
        </el-select>
      </div>
    </div>

    <template #footer>
      <el-button @click="cancelStatusFlow">取消</el-button>
      <el-button type="primary" @click="confirmStatusFlow">确认流转</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.flow-tip {
  font-size: 13px;
  color: #374151;
  margin-bottom: 12px;
}
.flow-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.form-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}
</style>
