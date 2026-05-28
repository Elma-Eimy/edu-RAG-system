<template>
  <div class="login-container">
    <!-- Centered Glassmorphism Card -->
    <div class="login-card glass-panel">
      <div class="card-header">
        <div class="logo"><i class="ph ph-graduation-cap"></i></div>
        <h1>SmartEdu</h1>
        <p class="subtitle">智能教育系统 · 检索增强问答中枢</p>
      </div>

      <!-- Error Alert Banner -->
      <transition name="slide-down">
        <div class="alert alert-danger" v-if="errorMessage">
          <span><i class="ph ph-warning"></i></span> {{ errorMessage }}
        </div>
      </transition>

      <!-- Login Form -->
      <form @submit.prevent="handleLogin" class="login-form">
        <div class="form-group">
          <label class="form-label" for="username">用户名</label>
          <div class="input-wrapper">
            <span class="input-icon"><i class="ph ph-user"></i></span>
            <input 
              type="text" 
              id="username" 
              v-model="username" 
              class="form-control" 
              placeholder="请输入用户名" 
              required
              :disabled="loading"
            />
          </div>
        </div>

        <div class="form-group">
          <label class="form-label" for="password">密码</label>
          <div class="input-wrapper">
            <span class="input-icon"><i class="ph ph-lock"></i></span>
            <input 
              type="password" 
              id="password" 
              v-model="password" 
              class="form-control" 
              placeholder="请输入密码" 
              required
              :disabled="loading"
            />
          </div>
        </div>

        <button type="submit" class="btn btn-primary submit-btn" :disabled="loading">
          <span class="spinner" v-if="loading"><i class="ph ph-spinner"></i></span>
          <span v-else>安全登录</span>
        </button>
      </form>

      <!-- Switch to Register Link -->
      <div class="card-footer">
        <p>还没有账号？ <router-link to="/register" class="link">立即创建账户</router-link></p>
      </div>

      <!-- Quick Simulation Drawer (Collapsible) -->
      <div class="simulation-drawer" :class="{ open: showSimulation }">
        <button class="simulation-toggle" @click="showSimulation = !showSimulation">
          {{ showSimulation ? '隐藏快捷演示通道' : '⚡ 展开快捷演示通道 (无需配置后端)' }}
        </button>
        <div class="simulation-content" v-if="showSimulation">
          <p class="drawer-desc">点击下方按钮可直接写入 Mock 角色数据并体验系统完整交互：</p>
          <div class="sim-buttons">
            <button class="btn btn-secondary sim-btn sim-student" @click="simulateLogin('student')">
              🏫 学生端演示
            </button>
            <button class="btn btn-secondary sim-btn sim-teacher" @click="simulateLogin('teacher')">
              📚 教师端演示
            </button>
            <button class="btn btn-secondary sim-btn sim-admin" @click="simulateLogin('admin')">
              🛡️ 管理员演示
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'
import { api } from '../utils/api'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMessage = ref('')
const showSimulation = ref(false)

// Real Authentication Call (OAuth2 Form Formatted)
const handleLogin = async () => {
  loading.value = true
  errorMessage.value = ''
  
  try {
    const params = new URLSearchParams()
    params.append('username', username.value)
    params.append('password', password.value)

    // Call oauth token endpoint
    const tokenResponse = await api.post('/users/login/access-token', params.toString(), {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    })

    // Save token
    authStore.setToken(tokenResponse.access_token)

    // Fetch user profile info
    const userProfile = await api.get('/users/me')
    authStore.setUser(userProfile)

    // Route based on role
    redirectUser(userProfile.role)
  } catch (error) {
    errorMessage.value = error.message || '登录失败，请检查账号和密码。'
  } finally {
    loading.value = false
  }
}

// Simulated bypass for quick demonstration without backend setup
const simulateLogin = (role) => {
  authStore.setToken('mock-jwt-bypass-token')
  authStore.setUser({
    id: 99,
    username: `demo_${role}`,
    email: `${role}_demo@smartedu.edu`,
    role: role,
    status: 'active'
  })
  redirectUser(role)
}

const redirectUser = (role) => {
  if (role === 'student') router.push('/student')
  else if (role === 'teacher') router.push('/teacher')
  else if (role === 'admin') router.push('/admin')
  else router.push('/login')
}
</script>

<style scoped>
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  width: 100%;
  background: radial-gradient(circle at 10% 20%, rgba(241, 245, 249, 1) 0%, rgba(226, 232, 240, 1) 90%);
  padding: 1.5rem;
}

.login-card {
  width: 100%;
  max-width: 440px;
  border-radius: var(--radius-lg);
  padding: 2.5rem;
  background-color: rgba(255, 255, 255, 0.75);
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.card-header {
  text-align: center;
}

.logo {
  font-size: 3.5rem;
  margin-bottom: 0.5rem;
}

.card-header h1 {
  font-size: 2rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.5px;
}

.subtitle {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 0.875rem;
  font-size: 1rem;
  color: var(--text-muted);
  pointer-events: none;
}

.form-control {
  width: 100%;
  padding-left: 2.5rem;
}

.submit-btn {
  margin-top: 0.5rem;
  width: 100%;
  padding: 0.75rem;
  font-size: 0.95rem;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
}

.submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.spinner {
  display: inline-block;
  animation: rotate 1.5s linear infinite;
  margin-right: 0.5rem;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.card-footer {
  text-align: center;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.link {
  font-weight: 600;
  color: var(--color-primary);
}

.link:hover {
  text-decoration: underline;
}

/* Alert styles */
.alert {
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.alert-danger {
  background-color: var(--color-danger-bg);
  color: var(--color-danger);
  border: 1px solid rgba(220, 38, 38, 0.15);
}

/* Simulation Drawer */
.simulation-drawer {
  border-top: 1px solid var(--border-color);
  padding-top: 1.25rem;
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.simulation-toggle {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  text-align: center;
  transition: color 0.2s ease;
}

.simulation-toggle:hover {
  color: var(--color-primary);
}

.drawer-desc {
  font-size: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.4;
  margin-bottom: 0.5rem;
}

.sim-buttons {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.sim-btn {
  padding: 0.5rem;
  font-size: 0.8rem;
  width: 100%;
  justify-content: flex-start;
  transition: all 0.2s ease;
}

.sim-student:hover {
  border-color: var(--color-success);
  color: var(--color-success);
  background-color: var(--color-success-bg);
}

.sim-teacher:hover {
  border-color: var(--color-warning);
  color: var(--color-warning);
  background-color: var(--color-warning-bg);
}

.sim-admin:hover {
  border-color: var(--color-danger);
  color: var(--color-danger);
  background-color: var(--color-danger-bg);
}

/* Transitions */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.2s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  transform: translateY(-8px);
  opacity: 0;
}
</style>
