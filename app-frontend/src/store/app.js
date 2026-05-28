import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    // Default to true (Sandbox Mock enabled) for immediate demo
    useMock: localStorage.getItem('use_mock') !== 'false'
  }),
  actions: {
    toggleMock() {
      this.useMock = !this.useMock
      localStorage.setItem('use_mock', this.useMock)
    }
  }
})
