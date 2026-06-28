import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    // 默认为 false（默认启用实时模式）
    useMock: false
  }),
  actions: {
    toggleMock() {
      // 已完全禁用 Mock 模式的切换
      this.useMock = false
      localStorage.setItem('use_mock', 'false')
    }
  }
})
