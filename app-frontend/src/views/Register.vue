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
      <transition name="slide-down">
        <div class="alert alert-success" v-if="codeSuccessMessage">
          <span><i class="ph ph-check-circle"></i></span> {{ codeSuccessMessage }}
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
          <div class="input-wrapper email-send-wrapper">
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
            <button 
              type="button" 
              class="btn btn-secondary send-code-btn" 
              @click="sendVerificationCode" 
              :disabled="loading || countdown > 0 || !email"
            >
              {{ countdown > 0 ? `${countdown}s 后重新获取` : '获取验证码' }}
            </button>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label" for="verificationCode">邮箱验证码</label>
          <div class="input-wrapper">
            <span class="input-icon"><i class="ph ph-key"></i></span>
            <input 
              type="text" 
              id="verificationCode" 
              v-model="verificationCode" 
              class="form-control" 
              placeholder="请输入 6 位验证码" 
              required
              maxlength="6"
              minlength="6"
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

        <!-- Teacher Specific Fields -->
        <transition name="fade">
          <div v-if="role === 'teacher'" class="teacher-fields-group">
            <div class="form-group">
              <label class="form-label" for="realName">真实姓名</label>
              <div class="input-wrapper">
                <span class="input-icon"><i class="ph ph-identification-card"></i></span>
                <input 
                  type="text" 
                  id="realName" 
                  v-model="realName" 
                  class="form-control" 
                  placeholder="请输入您的真实姓名" 
                  required
                  :disabled="loading"
                />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label" for="schoolName">学校名称</label>
              <div class="input-wrapper">
                <span class="input-icon"><i class="ph ph-buildings"></i></span>
                <input 
                  type="text" 
                  id="schoolName" 
                  v-model="schoolName" 
                  class="form-control" 
                  placeholder="请输入您所在的学校名称" 
                  required
                  :disabled="loading"
                />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label" for="credentialCode">工作证号 / 教师资格证号</label>
              <div class="input-wrapper">
                <span class="input-icon"><i class="ph ph-number-square-one"></i></span>
                <input 
                  type="text" 
                  id="credentialCode" 
                  v-model="credentialCode" 
                  class="form-control" 
                  placeholder="请输入证件编号" 
                  required
                  :disabled="loading"
                />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">资质证件照片上传</label>
              <div class="file-upload-wrapper">
                <input 
                  type="file" 
                  id="credentialFile" 
                  @change="handleFileUpload" 
                  accept="image/*" 
                  class="file-input-hidden" 
                  ref="fileInputRef"
                  :required="!credentialImageUrl"
                />
                <button 
                  type="button" 
                  class="btn btn-secondary upload-trigger" 
                  @click="triggerFileInput"
                  :disabled="loading || uploadLoading"
                >
                  <span class="spinner" v-if="uploadLoading"><i class="ph ph-spinner"></i></span>
                  <i class="ph ph-upload-simple" v-else></i>
                  {{ credentialImageUrl ? '重新选择并上传证件照' : '上传证件照片' }}
                </button>
                <div v-if="credentialImageUrl" class="image-preview-container">
                  <img :src="getFullImageUrl(credentialImageUrl)" alt="证件预览" class="credential-preview" />
                  <span class="upload-success-text"><i class="ph ph-check-circle"></i> 上传成功</span>
                </div>
              </div>
            </div>
          </div>
        </transition>

        <button type="submit" class="btn btn-primary submit-btn" :disabled="loading || uploadLoading">
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
import { ref, onUnmounted } from 'vue'
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
const codeSuccessMessage = ref('')

// Verification OTP state
const verificationCode = ref('')
const countdown = ref(0)
const countdownTimer = ref(null)

// Teacher registration state
const realName = ref('')
const schoolName = ref('')
const credentialCode = ref('')
const credentialImageUrl = ref('')
const fileInputRef = ref(null)
const uploadLoading = ref(false)

onUnmounted(() => {
  if (countdownTimer.value) {
    clearInterval(countdownTimer.value)
  }
})

const sendVerificationCode = async () => {
  if (!email.value) {
    errorMessage.value = '请先输入邮箱地址'
    return
  }
  try {
    loading.value = true
    errorMessage.value = ''
    await api.post('/users/send-verification-code', { email: email.value.trim() })
    codeSuccessMessage.value = '验证码发送成功，开发环境已输出至后端控制台日志'
    setTimeout(() => {
      codeSuccessMessage.value = ''
    }, 5000)
    
    // Start countdown
    if (countdownTimer.value) {
      clearInterval(countdownTimer.value)
    }
    countdown.value = 60
    countdownTimer.value = setInterval(() => {
      if (countdown.value > 1) {
        countdown.value--
      } else {
        countdown.value = 0
        clearInterval(countdownTimer.value)
        countdownTimer.value = null
      }
    }, 1000)
  } catch (error) {
    errorMessage.value = error.message || '发送验证码失败，邮箱可能已被占用。'
  } finally {
    loading.value = false
  }
}

const triggerFileInput = () => {
  if (fileInputRef.value) {
    fileInputRef.value.click()
  }
}

const handleFileUpload = async (event) => {
  const file = event.target.files[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)

  uploadLoading.value = true
  errorMessage.value = ''
  try {
    const res = await api.post('/users/upload-credential', formData)
    credentialImageUrl.value = res.credential_image_url
  } catch (error) {
    errorMessage.value = error.message || '证件上传失败，请确保文件是图片格式。'
  } finally {
    uploadLoading.value = false
  }
}

const getFullImageUrl = (relativeUrl) => {
  if (!relativeUrl) return ''
  if (relativeUrl.startsWith('http')) return relativeUrl
  const base = api.baseUrl.replace(/\/api\/v1\/?$/, '')
  return `${base}${relativeUrl}`
}

const handleRegister = async () => {
  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''
  codeSuccessMessage.value = ''
  
  try {
    const signupData = {
      username: username.value.trim(),
      email: email.value.trim(),
      password: password.value,
      role: role.value,
      verification_code: verificationCode.value.trim()
    }

    if (role.value === 'teacher') {
      if (!realName.value || !schoolName.value || !credentialCode.value || !credentialImageUrl.value) {
        throw new Error('教师注册必须填写真实姓名、学校、证件号并上传证件照')
      }
      signupData.real_name = realName.value.trim()
      signupData.school_name = schoolName.value.trim()
      signupData.credential_code = credentialCode.value.trim()
      signupData.credential_image_url = credentialImageUrl.value
    }

    // Call register endpoint
    await api.post('/users/register', signupData)

    if (role.value === 'teacher') {
      successMessage.value = '教师资质提交成功！账户暂时冻结，请联系管理员审批后再登录。正在跳转...'
    } else {
      successMessage.value = '注册成功！正在引导您前往登录页...'
    }
    
    // Auto redirect to login after 3 seconds
    setTimeout(() => {
      router.push('/login')
    }, 3000)
  } catch (error) {
    errorMessage.value = error.message || '注册失败，验证码错误或用户名/邮箱已被占用。'
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
  transform: translateY(-10px);
  opacity: 0;
}

/* Email Verification Code Send Layout */
.email-send-wrapper {
  display: flex;
  gap: 0.5rem;
}

.email-send-wrapper .form-control {
  flex-grow: 1;
}

.send-code-btn {
  white-space: nowrap;
  padding: 0 0.75rem;
  font-size: 0.8rem;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background-color: var(--bg-hover);
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.send-code-btn:hover:not(:disabled) {
  background-color: var(--border-color);
}

.send-code-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Teacher fields layout */
.teacher-fields-group {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding-top: 0.5rem;
  border-top: 1px dashed var(--border-color);
  margin-top: 0.5rem;
}

/* File Upload styling */
.file-upload-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.25rem;
}

.file-input-hidden {
  display: none;
}

.upload-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.625rem;
  font-size: 0.85rem;
  cursor: pointer;
}

.image-preview-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background-color: var(--bg-hover);
  border-radius: var(--radius-md);
  border: 1px dashed var(--border-color);
}

.credential-preview {
  max-width: 100%;
  max-height: 160px;
  object-fit: contain;
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
}

.upload-success-text {
  font-size: 0.75rem;
  color: var(--color-success);
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-weight: 600;
}
</style>
