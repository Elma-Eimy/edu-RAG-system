<template>
  <div class="student-dashboard">
    <!-- Header Controls -->
    <div class="dashboard-header animate-fade">
      <div class="welcome-section">
        <h2>我的班级看板</h2>
        <p class="subtitle">管理您的班级关联，并与绑定教材的 AI 进行交互式学习</p>
      </div>
      <!-- Floating-style main action button -->
      <button class="btn btn-primary join-class-trigger" @click="openJoinModal">
        <span><i class="ph ph-plus-circle"></i></span> 加入新班级
      </button>
    </div>

    <!-- Feedback Message Banner -->
    <transition name="slide-down">
      <div class="alert" :class="alertClass" v-if="globalMessage">
        <span><i :class="globalMessage.type === 'success' ? 'ph ph-check-circle' : 'ph ph-warning'"></i></span>
        {{ globalMessage.text }}
      </div>
    </transition>

    <!-- Main Content Panel: Class Cards Grid -->
    <div class="class-grid" v-if="classes.length > 0">
      <div v-for="cls in classes" :key="cls.class_id" class="class-card card animate-card">
        <div class="card-header">
          <div class="class-avatar"><i class="ph ph-school"></i></div>
          <div class="title-area">
            <h3>{{ cls.class_name }}</h3>
            <span class="class-code-label">班级码: <code class="class-code">{{ cls.class_code }}</code></span>
          </div>
          <span class="badge" :class="getStatusBadgeClass(cls.application_status)">
            {{ getStatusDisplayName(cls.application_status) }}
          </span>
        </div>

        <div class="card-body">
          <div class="detail-row">
            <span class="label">授课教师 ID:</span>
            <span class="value">#{{ cls.teacher_id }}</span>
          </div>
          <div class="detail-row">
            <span class="label">申请单号:</span>
            <span class="value">#{{ cls.application_id }}</span>
          </div>
        </div>

        <div class="card-actions">
          <!-- Active class action -->
          <router-link 
            v-if="cls.application_status === 'approved'" 
            to="/student/chat" 
            class="btn btn-primary action-btn"
          >
            <i class="ph ph-chats"></i> 进入 AI 问答
          </router-link>
          
          <!-- Pending or Rejected status actions -->
          <div v-else class="status-placeholder">
            <span>
              <i :class="cls.application_status === 'pending' ? 'ph ph-hourglass-high' : 'ph ph-x-circle'"></i>
              {{ cls.application_status === 'pending' ? ' 审批中，请耐心等待' : ' 申请已被教师拒绝' }}
            </span>
          </div>

          <!-- Quit class/Withdraw request action -->
          <button class="btn-quit" @click="confirmQuit(cls)" :title="cls.application_status === 'approved' ? '退出班级' : '撤回申请'">
            <i class="ph ph-trash"></i> {{ cls.application_status === 'approved' ? '退课' : '撤回' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div class="empty-state glass-panel animate-fade" v-else>
      <div class="empty-illustration"><i class="ph ph-backpack"></i></div>
      <h3>您当前尚未加入任何班级</h3>
      <p>加入班级后，您可以访问由教师授权的 PDF 教材并开启 AI 流式问答。</p>
      <button class="btn btn-primary" @click="openJoinModal">立即加入第一个班级</button>
    </div>

    <!-- Glassmorphic Modal overlay (Backdrop Blur) -->
    <transition name="fade">
      <div class="modal-overlay" v-if="showJoinModal" @click.self="closeJoinModal">
        <div class="modal-card glass-panel animate-zoom">
          <div class="modal-header">
            <h3>加入新班级</h3>
            <button class="close-btn" @click="closeJoinModal"><i class="ph ph-x"></i></button>
          </div>

          <!-- Modal Error Banner -->
          <transition name="slide-down">
            <div class="alert alert-danger modal-alert" v-if="modalError">
              <span><i class="ph ph-warning"></i></span> {{ modalError }}
            </div>
          </transition>

          <form @submit.prevent="handleJoinClass" class="modal-form">
            <div class="form-group">
              <label class="form-label" for="classCode">6位班级邀请码</label>
              <input 
                type="text" 
                id="classCode" 
                v-model="classCode" 
                class="form-control code-input" 
                placeholder="请输入 6 位大写字母或数字" 
                required
                maxlength="6"
                autocomplete="off"
                :disabled="modalLoading"
              />
              <span class="input-helper">班级邀请码由教师创建，通常为大写字母和数字组成。</span>
            </div>

            <div class="modal-actions">
              <button type="button" class="btn btn-secondary" @click="closeJoinModal" :disabled="modalLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary submit-btn" :disabled="modalLoading">
                <span class="spinner" v-if="modalLoading"><i class="ph ph-spinner"></i></span>
                <span v-else>提交申请</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </transition>

    <!-- Confirmation Modal Overlay -->
    <transition name="fade">
      <div class="modal-overlay confirm-overlay" v-if="showConfirmModal" @click.self="closeConfirmModal">
        <div class="modal-card confirm-card glass-panel animate-zoom">
          <h3>确认操作</h3>
          <p class="confirm-message">
            您确定要{{ selectedClass?.application_status === 'approved' ? '退出班级' : '撤销申请' }} 
            <strong>“{{ selectedClass?.class_name }}”</strong> 吗？
          </p>
          <div class="confirm-actions">
            <button class="btn btn-secondary" @click="closeConfirmModal">取消</button>
            <button class="btn btn-danger" @click="handleQuitClass">确认</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '../../utils/api'

// Classes List State
const classes = ref([])
const showJoinModal = ref(false)
const showConfirmModal = ref(false)
const classCode = ref('')
const selectedClass = ref(null)

const modalLoading = ref(false)
const modalError = ref(false)
const globalMessage = ref(null)

// Default Mock Data for immediate offline demonstration
const mockClasses = [
  {
    application_id: 101,
    class_id: 1,
    class_name: '高等数学 A 班',
    class_code: 'AB12CD',
    teacher_id: 5,
    application_status: 'approved'
  },
  {
    application_id: 102,
    class_id: 2,
    class_name: '线性代数 B 班',
    class_code: 'XY99ZZ',
    teacher_id: 6,
    application_status: 'pending'
  }
]

// Alert helper classes
const alertClass = computed(() => {
  if (!globalMessage.value) return ''
  return globalMessage.value.type === 'success' ? 'alert-success' : 'alert-danger'
})

// Load classes
const fetchClasses = async () => {
  try {
    const res = await api.get('/classes/my-classes')
    classes.value = res
  } catch (error) {
    console.warn('Backend API connection failed, falling back to mock data for student dashboard demonstration.')
    classes.value = [...mockClasses]
  }
}

onMounted(() => {
  fetchClasses()
})

// Status badge styling mapper
const getStatusBadgeClass = (status) => {
  const mapping = {
    approved: 'badge-success',
    pending: 'badge-warning',
    rejected: 'badge-danger'
  }
  return mapping[status] || ''
}

const getStatusDisplayName = (status) => {
  const mapping = {
    approved: '已通过',
    pending: '审批中',
    rejected: '已拒绝'
  }
  return mapping[status] || status
}

// Modal open/close controls
const openJoinModal = () => {
  classCode.value = ''
  modalError.value = ''
  showJoinModal.value = true
}

const closeJoinModal = () => {
  showJoinModal.value = false
}

// Perform Join request
const handleJoinClass = async () => {
  modalLoading.value = true
  modalError.value = ''
  
  // Format code to uppercase and trim whitespaces
  const formattedCode = classCode.value.trim().toUpperCase()
  
  if (formattedCode.length !== 6) {
    modalError.value = '邀请码必须为 6 位。'
    modalLoading.value = false
    return
  }

  try {
    // Attempt actual backend POST request
    const response = await api.post('/classes/join', { class_code: formattedCode })
    
    closeJoinModal()
    showSuccessToast(response.message || '申请成功已提交！')
    fetchClasses()
  } catch (error) {
    // If backend offline or code invalid, do mock fallback
    if (error.message.includes('请求失败') || error.message.includes('Failed to fetch')) {
      // Mock validation
      const alreadyExists = classes.value.some(c => c.class_code === formattedCode)
      if (alreadyExists) {
        modalError.value = '您已经申请过该班级，请勿重复申请。'
      } else {
        // Successful mock addition
        const newMock = {
          application_id: Math.floor(Math.random() * 1000) + 100,
          class_id: classes.value.length + 1,
          class_name: `模拟自主班级 ${formattedCode}`,
          class_code: formattedCode,
          teacher_id: Math.floor(Math.random() * 10) + 1,
          application_status: 'pending'
        }
        classes.value.push(newMock)
        closeJoinModal()
        showSuccessToast('申请已成功提交（模拟沙盒拦截模式）！')
      }
    } else {
      modalError.value = error.message || '申请加入失败，请检查班级码。'
    }
  } finally {
    modalLoading.value = false
  }
}

// Delete / Quit Class Confirmation control
const confirmQuit = (cls) => {
  selectedClass.value = cls
  showConfirmModal.value = true
}

const closeConfirmModal = () => {
  showConfirmModal.value = false
  selectedClass.value = null
}

const handleQuitClass = async () => {
  if (!selectedClass.value) return

  const classId = selectedClass.value.class_id
  const isApproved = selectedClass.value.application_status === 'approved'

  try {
    // Call backend endpoint
    await api.delete(`/classes/${classId}/quit`)
    
    showSuccessToast(isApproved ? '退出班级成功。' : '申请撤销成功。')
    fetchClasses()
  } catch (error) {
    // Mock simulation deletion
    classes.value = classes.value.filter(c => c.class_id !== classId)
    showSuccessToast(isApproved ? '成功退出班级（模拟沙盒拦截模式）。' : '成功撤销申请（模拟沙盒拦截模式）。')
  } finally {
    closeConfirmModal()
  }
}

// Display temporary floating Toast alert
const showSuccessToast = (text) => {
  globalMessage.value = { type: 'success', text }
  setTimeout(() => {
    globalMessage.value = null
  }, 4000)
}
</script>

<style scoped>
.student-dashboard {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  width: 100%;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 1.25rem;
}

.welcome-section h2 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.subtitle {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.join-class-trigger {
  padding: 0.65rem 1.25rem;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
}

/* Card Grid Layout */
.class-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.5rem;
}

.class-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: relative;
  overflow: hidden;
}

.class-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--color-primary), var(--color-accent));
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  position: relative;
}

.class-avatar {
  font-size: 1.75rem;
  background-color: var(--bg-hover);
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.title-area {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
  min-width: 0;
}

.title-area h3 {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.class-code-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin-top: 0.1rem;
}

.class-code {
  font-size: 0.75rem;
  background-color: var(--bg-hover);
  padding: 1px 4px;
  border-radius: 4px;
  color: var(--color-primary);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  background-color: var(--bg-hover);
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  font-size: 0.8rem;
}

.detail-row {
  display: flex;
  justify-content: space-between;
}

.detail-row .label {
  color: var(--text-muted);
}

.detail-row .value {
  color: var(--text-secondary);
  font-weight: 500;
}

.card-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-top: auto;
}

.action-btn {
  flex-grow: 1;
  padding: 0.5rem;
  font-size: 0.825rem;
}

.status-placeholder {
  flex-grow: 1;
  font-size: 0.8rem;
  color: var(--text-muted);
  background-color: var(--bg-hover);
  border-radius: var(--radius-md);
  padding: 0.5rem;
  text-align: center;
  border: 1px dashed var(--border-color);
}

.btn-quit {
  background: none;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-quit:hover {
  background-color: var(--color-danger-bg);
  border-color: rgba(220, 38, 38, 0.3);
  color: var(--color-danger);
}

/* Empty State Dashboard style */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 4rem 2rem;
  border-radius: var(--radius-lg);
  background-color: rgba(255, 255, 255, 0.7);
  max-width: 580px;
  margin: 2rem auto;
  gap: 1rem;
}

.empty-illustration {
  font-size: 4rem;
}

.empty-state h3 {
  font-size: 1.25rem;
  font-weight: 600;
}

.empty-state p {
  font-size: 0.875rem;
  color: var(--text-muted);
  max-width: 420px;
  line-height: 1.5;
  margin-bottom: 0.5rem;
}

/* Glassmorphic Modal Layout */
.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.25);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  z-index: 1000;
}

.modal-card {
  width: 100%;
  max-width: 440px;
  background-color: rgba(255, 255, 255, 0.85);
  border-radius: var(--radius-lg);
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
}

.close-btn {
  background: none;
  border: none;
  font-size: 0.9rem;
  cursor: pointer;
  padding: 0.25rem;
  opacity: 0.6;
  transition: opacity 0.2s ease;
}

.close-btn:hover {
  opacity: 1;
}

.modal-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.code-input {
  text-align: center;
  font-size: 1.5rem;
  letter-spacing: 0.5rem;
  text-transform: uppercase;
  font-family: ui-monospace, monospace;
  padding: 0.75rem;
}

.code-input::placeholder {
  letter-spacing: normal;
  font-size: 0.95rem;
  font-family: var(--font-sans);
}

.input-helper {
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.4;
  margin-top: 0.25rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.modal-actions .btn {
  padding: 0.5rem 1.25rem;
}

/* Confirm modal style */
.confirm-card {
  max-width: 380px;
  text-align: center;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.confirm-message {
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.confirm-actions {
  display: flex;
  justify-content: center;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.confirm-actions .btn {
  padding: 0.5rem 1.25rem;
  font-size: 0.85rem;
}

/* Toast alert style */
.alert {
  padding: 0.75rem 1.25rem;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  box-shadow: var(--shadow-sm);
  border: 1px solid transparent;
}

.alert-success {
  background-color: var(--color-success-bg);
  color: var(--color-success);
  border-color: rgba(5, 150, 105, 0.15);
}

.alert-danger {
  background-color: var(--color-danger-bg);
  color: var(--color-danger);
  border-color: rgba(220, 38, 38, 0.15);
}

.modal-alert {
  margin-bottom: -0.5rem;
}

.spinner {
  display: inline-block;
  animation: rotate 1.5s linear infinite;
  margin-right: 0.25rem;
}

/* micro animations */
.animate-fade {
  animation: fadeIn 0.3s ease-out;
}

.animate-card {
  animation: slideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-zoom {
  animation: zoomIn 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes zoomIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* Transitions */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.slide-down-enter-active, .slide-down-leave-active {
  transition: all 0.25s ease;
}
.slide-down-enter-from, .slide-down-leave-to {
  transform: translateY(-10px);
  opacity: 0;
}
</style>
