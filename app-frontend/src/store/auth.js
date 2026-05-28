import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
  state: () => {
    let savedUser = null
    try {
      const userStr = localStorage.getItem('user')
      savedUser = userStr && userStr !== 'undefined' ? JSON.parse(userStr) : null
    } catch (e) {
      console.error('Failed to parse saved user from localStorage:', e)
      localStorage.removeItem('user')
      localStorage.removeItem('token')
    }
    return {
      token: localStorage.getItem('token') || null,
      user: savedUser
    }
  },
  getters: {
    isAuthenticated: (state) => !!state.token,
    userRole: (state) => state.user?.role || null
  },
  actions: {
    setToken(token) {
      this.token = token
      localStorage.setItem('token', token)
    },
    setUser(user) {
      this.user = user
      localStorage.setItem('user', JSON.stringify(user))
    },
    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    }
  }
})
