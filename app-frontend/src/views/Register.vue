<template>
  <div class="register-container">
    <!-- Centered Glassmorphism Card -->
    <div class="register-card glass-panel">
      <div class="card-header">
        <div class="logo"><i class="ph ph-graduation-cap"></i></div>
        <h1>创建账户</h1>
        <p class="subtitle">智能教育系统 · 知识库交互网关</p>
      </div>

      <!-- Alert Banner -->
      <transition name="slide-down">
        <div class="alert alert-danger" v-if="errorMessage">
          <span><i class="ph ph-warning"></i></span> {{ errorMessage }}
        </div>
      </transition>
      <transition name="slide-down">
        <div class="alert alert-success" v-if="successMessage">
          <span><i class="ph ph-check-circle"></i></span> {{ successMessage }}
        </div>
      </transition>

      <!-- Register Form -->
      <form @submit.prevent="handleRegister" class="register-form" v-if="!successMessage">
        <!-- Role Tabs Selector -->
        <div class="role-selector">
          <button 
            type="button" 
            class="role-tab" 
            :class="{ active: role === 'student' }"
            @click="role = 'student'"
            :disabled="loading"
          >
            <i class="ph ph-student"></i> 我是学生
          </button>
          <button 
            type="button" 
            class="role-tab" 
            :class="{ active: role === 'teacher' }"
            @click="role = 'teacher'"
            :disabled="loading"
          >
            <i class="ph ph-chalkboard-teacher"></i> 我是教师
          </button>
        </div>

        <div class="form-group">
          <label class="form-label" for="username">用户名</label>
          <div class="input-wrapper">
            <span class="input-icon"><i class="ph ph-user"></i></span>
            <input 
              type="text" 
              id="username" 
              v-model="username" 
              class="form-control" 
              placeholder="请输入用户名（3-50 字符）" 
              required
              minlength="3"
              maxlength="50"
              :disabled="loading"
            />
          </div>
        </div>

        <div class="form-group">
          <label class="form-label" for="email">邮箱地址</label>
          <div class="input-wrapper">
            <span class="input-icon"><i class="ph ph-envelope"></i></span>
            <input 
              type="email" 
              id="email" 
              v-model="email" 
              class="form-control" 
              placeholder="请输入电子邮箱" 
              required
              :disabled="loading"
            />
          </div>
        </div>

        <div class="form-group">
          <label class="form-label" for="password">安全密码</label>
          <div class="input-wrapper">
            <span class="input-icon"><i class="ph ph-lock"></i></span>
            <input 
              type="password" 
              id="password" 
              v-model="password" 
              class="form-control" 
              placeholder="请输入密码（最少 6 位）" 
              required
              minlength="6"
              :disabled="loading"
            />
          </div>
        </div>

        <button type="submit" class="btn btn-primary submit-btn" :disabled="loading">
          <span class="spinner" v-if="loading"><i class="ph ph-spinner"></i></span>
          <span v-else>立即注册</span>
        </button>
      </form>

      <!-- Successful registration redirect layout -->
      <div class="success-redirect" v-else>
        <p class="redirect-text">正在为您跳转到登录页面...</p>
        <router-link to="/login" class="btn btn-primary redirect-btn">立即登录</router-link>
      </div>

      <!-- Switch to Login Link -->
      <div class="card-footer" v-if="!successMessage">
        <p>已有账号？ <router-link to="/login" class="link">立即安全登录</router-link></p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../utils/api'

const router = useRouter()

const username = ref('')
const email = ref('')
const password = ref('')
const role = ref('student')
const loading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

const handleRegister = async () => {
  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''
  
  try {
    const signupData = {
      username: username.value,
      email: email.value,
      password: password.value,
      role: role.value
    }

    // Call register endpoint
    await api.post('/users/register', signupData)

    successMessage.value = '注册成功！正在引导您前往登录页...'
    
    // Auto redirect to login after 2 seconds
    setTimeout(() => {
      router.push('/login')
    }, 2000)
  } catch (error) {
    errorMessage.value = error.message || '注册失败，用户名或邮箱可能已被占用。'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  width: 100%;
  background: radial-gradient(circle at 10% 20%, rgba(241, 245, 249, 1) 0%, rgba(226, 232, 240, 1) 90%);
  padding: 1.5rem;
}

.register-card {
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

/* Role Selector Tabs */
.role-selector {
  display: flex;
  background-color: var(--bg-hover);
  border-radius: var(--radius-md);
  padding: 0.25rem;
  border: 1px solid var(--border-color);
  margin-bottom: 0.5rem;
}

.role-tab {
  flex: 1;
  border: none;
  background: none;
  padding: 0.625rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-secondary);
  border-radius: calc(var(--radius-md) - 2px);
  cursor: pointer;
  transition: all 0.2s ease;
}

.role-tab.active {
  background-color: #ffffff;
  color: var(--color-primary);
  box-shadow: var(--shadow-sm);
}

.register-form {
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

/* Success Redirect Panel */
.success-redirect {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.25rem;
  padding: 1rem 0;
  text-align: center;
}

.redirect-text {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.redirect-btn {
  width: 100%;
  padding: 0.75rem;
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

.alert-success {
  background-color: var(--color-success-bg);
  color: var(--color-success);
  border: 1px solid rgba(5, 150, 105, 0.15);
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
