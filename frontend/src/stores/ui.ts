// 瞬时 UI 偏好（localStorage 持久化，非业务数据，符合 PRD 4.6）
import { defineStore } from 'pinia'

export const useUiStore = defineStore('ui', {
  state: () => ({
    includeEnded: localStorage.getItem('ui_include_ended') === '1',
  }),
  actions: {
    toggleIncludeEnded() {
      this.includeEnded = !this.includeEnded
      localStorage.setItem('ui_include_ended', this.includeEnded ? '1' : '0')
    },
  },
})
