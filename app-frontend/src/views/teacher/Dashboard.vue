<template>
  <div class="teacher-dashboard">
    <!-- View Header -->
    <div class="dashboard-header animate-fade">
      <div class="welcome-section">
        <h2>班级工作台</h2>
        <p class="subtitle">管理您的授课班级、发布专属班级码，以及分配绑定知识库教材</p>
      </div>
      <button class="btn btn-primary create-class-trigger" @click="openCreateModal">
        <span><i class="ph ph-plus-circle"></i></span> 创建新班级
      </button>
    </div>

    <!-- Alert Notification Banner -->
    <transition name="slide-down">
      <div class="alert" :class="alertClass" v-if="globalMessage">
        <span><i :class="globalMessage.type === 'success' ? 'ph ph-check-circle' : 'ph ph-warning'"></i></span>
        {{ globalMessage.text }}
      </div>
    </transition>

    <!-- Classes Grid Area -->
    <div class="class-grid" v-if="classes.length > 0">
      <div v-for="cls in classes" :key="cls.id" class="class-card card animate-card">
        <div class="card-top">
          <div class="class-icon"><i class="ph ph-chalkboard"></i></div>
          <div class="title-details">
            <h3>{{ cls.name }}</h3>
            <!-- Hover Copy Class Code Container -->
            <div class="code-copy-container" @click="copyClassCode(cls.class_code)">
              <span class="code-label">班级邀请码:</span>
              <code class="class-code">{{ cls.class_code }}</code>
              
              <!-- Hover Micro Bubble -->
              <span class="copy-bubble" :class="{ copied: activeCopyCode === cls.class_code }">
                <i :class="activeCopyCode === cls.class_code ? 'ph ph-check' : 'ph ph-copy'"></i>
                {{ activeCopyCode === cls.class_code ? ' 已复制! ✓' : ' 点击复制' }}
              </span>
            </div>
          </div>
        </div>

        <div class="card-stats">
          <div class="stat-box">
            <span class="stat-val">{{ cls.students?.length || 0 }}</span>
            <span class="stat-label">已加学生</span>
          </div>
          <div class="stat-box">
            <span class="stat-val">{{ cls.textbooks?.length || 0 }}</span>
            <span class="stat-label">绑定教材</span>
          </div>
        </div>

        <!-- Linked resources list -->
        <div class="card-textbooks" v-if="cls.textbooks && cls.textbooks.length > 0">
          <span class="textbooks-title"><i class="ph ph-book-bookmark"></i> 关联教材:</span>
          <div class="textbooks-list">
            <span 
              v-for="tb in cls.textbooks" 
              :key="tb.id" 
              class="tb-tag"
            >
              {{ tb.title }}
            </span>
          </div>
        </div>
        <div class="card-textbooks empty-textbooks" v-else>
          <span><i class="ph ph-book-open"></i> 暂无授权教材，请前往教材库进行绑定授权</span>
        </div>

        <!-- Class Work controls -->
        <div class="card-actions">
          <router-link :to="`/teacher/class/${cls.id}`" class="btn btn-primary manage-btn">
            <i class="ph ph-users"></i> 学生与审批管理
          </router-link>
          <button class="btn-disband" @click="confirmDisband(cls)" title="解散班级">
            <i class="ph ph-trash"></i> 解散
          </button>
        </div>
      </div>
    </div>

    <!-- Empty Workspace State -->
    <div class="empty-state glass-panel animate-fade" v-else>
      <div class="empty-illustration"><i class="ph ph-school"></i></div>
      <h3>您名下暂无授课班级</h3>
      <p>创建一个班级以生成独一无二的 6 位“班级码”，让您的学生申请入班并获取教材阅读问答权限。</p>
      <button class="btn btn-primary" @click="openCreateModal">立即创建第一个班级</button>
    </div>

    <!-- Create Class Modal Overlay -->
    <transition name="fade">
      <div class="modal-overlay" v-if="showCreateModal" @click.self="closeCreateModal">
        <div class="modal-card glass-panel animate-zoom">
          <div class="modal-header">
            <h3>创建新班级</h3>
            <button class="close-btn" @click="closeCreateModal"><i class="ph ph-x"></i></button>
          </div>

          <form @submit.prevent="handleCreateClass" class="modal-form">
            <div class="form-group">
              <label class="form-label" for="className">班级名称</label>
              <input 
                type="text" 
                id="className" 
                v-model="newClassName" 
                class="form-control" 
                placeholder="请输入官方班级名称（例如：高等数学 A 班）" 
                required
                :disabled="modalLoading"
              />
              <span class="input-helper">系统将自动为新班级生成唯一的、防碰撞的 6 位大写邀请码。</span>
            </div>

            <div class="modal-actions">
              <button type="button" class="btn btn-secondary" @click="closeCreateModal" :disabled="modalLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary submit-btn" :disabled="modalLoading">
                <span class="spinner" v-if="modalLoading"><i class="ph ph-spinner"></i></span>
                <span v-else>立即创建</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </transition>

    <!-- Disband Class Confirmation Modal -->
    <transition name="fade">
      <div class="modal-overlay confirm-overlay" v-if="showConfirmDisband" @click.self="closeConfirmDisband">
        <div class="modal-card confirm-card glass-panel animate-zoom">
          <h3>解散班级警告</h3>
          <p class="confirm-message">
            您确定要彻底解散班级 <strong>“{{ classToDisband?.name }}”</strong> 吗？
            解散后，<strong>该班级的邀请码将作废</strong>，所有已加入的学生将被移出，绑定的教材授权将全部熔断解除，操作不可逆。
          </p>
          <div class="confirm-actions">
            <button class="btn btn-secondary" @click="closeConfirmDisband">取消</button>
            <button class="btn btn-danger" @click="handleDisbandClass">确认解散</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '../../utils/api'

// Dashboard State
const classes = ref([])
const showCreateModal = ref(false)
const showConfirmDisband = ref(false)

const newClassName = ref('')
const classToDisband = ref(null)

const modalLoading = ref(false)
const activeCopyCode = ref(null)
const globalMessage = ref(null)

// Default Mock Data for local workspace demonstration
const mockClasses = [
  {
    id: 1,
    name: '高等数学 A 班',
    class_code: 'AB12CD',
    textbooks: [
      { id: 3, title: '高等数学上册', status: 'success' }
    ],
    students: [
      { student_id: 10, username: 'lisi' },
      { student_id: 11, username: 'wangwu' }
    ]
  },
  {
    id: 2,
    name: '线性代数 B 班',
    class_code: 'XY99ZZ',
    textbooks: [],
    students: [
      { student_id: 12, username: 'zhaoliu' }
    ]
  }
]

// Alert styles
const alertClass = computed(() => {
  if (!globalMessage.value) return ''
  return globalMessage.value.type === 'success' ? 'alert-success' : 'alert-danger'
})

// Load Teacher Classes Dashboard
const fetchClasses = async () => {
  try {
    const res = await api.get('/classes/dashboard')
    classes.value = res.classes || []
  } catch (error) {
    console.warn('Backend API connection offline, falling back to mock classes dashboard.')
    classes.value = [...mockClasses]
  }
}

onMounted(() => {
  fetchClasses()
})

// Copy class code to clipboard with micro bubble flash
const copyClassCode = async (code) => {
  try {
    await navigator.clipboard.writeText(code)
    activeCopyCode.value = code
    
    // Reset bubble message after 2 seconds
    setTimeout(() => {
      if (activeCopyCode.value === code) {
        activeCopyCode.value = null
      }
    }, 2000)
  } catch (err) {
    console.error('Clipboard copy failed:', err)
  }
}

// Create class controls
const openCreateModal = () => {
  newClassName.value = ''
  showCreateModal.value = true
}

const closeCreateModal = () => {
  showCreateModal.value = false
}

const handleCreateClass = async () => {
  modalLoading.value = true
  try {
    const response = await api.post('/classes/', { name: newClassName.value.trim() })
    
    classes.value.push({
      ...response,
      textbooks: [],
      students: []
    })
    closeCreateModal()
    showSuccessToast(`班级 “${response.name}” 创建成功，班级邀请码为: ${response.class_code}。`)
  } catch (error) {
    // Sandbox mock bypass
    const generatedCode = Math.random().toString(36).substring(2, 8).toUpperCase()
    const mockNewClass = {
      id: classes.value.length + 1,
      name: newClassName.value.trim(),
      class_code: generatedCode,
      textbooks: [],
      students: []
    }
    classes.value.push(mockNewClass)
    closeCreateModal()
    showSuccessToast(`班级 “${mockNewClass.name}” 创建成功（模拟沙盒拦截，生成邀请码为: ${generatedCode}）！`)
  } finally {
    modalLoading.value = false
  }
}

// Disband class controls
const confirmDisband = (cls) => {
  classToDisband.value = cls
  showConfirmDisband.value = true
}

const closeConfirmDisband = () => {
  showConfirmDisband.value = false
  classToDisband.value = null
}

const handleDisbandClass = async () => {
  if (!classToDisband.value) return
  const id = classToDisband.value.id

  try {
    await api.delete(`/classes/${id}`)
    classes.value = classes.value.filter(c => c.id !== id)
    showSuccessToast('班级已成功解散。')
  } catch (error) {
    // Sandbox deletion
    classes.value = classes.value.filter(c => c.id !== id)
    showSuccessToast('班级已解散作废（模拟沙盒拦截模式）。')
  } finally {
    closeConfirmDisband()
  }
}

// Toast alerts helper
const showSuccessToast = (text) => {
  globalMessage.value = { type: 'success', text }
  setTimeout(() => {
    globalMessage.value = null
  }, 5000)
}
</script>

<style scoped>
.teacher-dashboard {
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

.dashboard-header h2 {
  font-size: 1.5rem;
  font-weight: 700;
}

.subtitle {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.create-class-trigger {
  padding: 0.65rem 1.25rem;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
}

/* Classes card grid layout */
.class-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
  gap: 1.5rem;
}

.class-card {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
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

.card-top {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.class-icon {
  font-size: 1.75rem;
  background-color: var(--bg-hover);
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.title-details {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex-grow: 1;
}

.title-details h3 {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Hover Micro Copy Bubble container */
.code-copy-container {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
  color: var(--text-muted);
  cursor: pointer;
  position: relative;
  width: fit-content;
  margin-top: 0.15rem;
}

.class-code {
  font-size: 0.75rem;
  font-family: ui-monospace, monospace;
  background-color: var(--bg-hover);
  padding: 1px 4px;
  border-radius: 4px;
  color: var(--color-primary);
  font-weight: 600;
  border: 1px solid var(--border-color);
  transition: all 0.2s ease;
}

.code-copy-container:hover .class-code {
  border-color: var(--color-primary);
  background-color: rgba(37, 99, 235, 0.02);
}

/* Micro copy tooltip bubble */
.copy-bubble {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%) translateY(4px);
  background-color: var(--text-primary);
  color: #ffffff;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.65rem;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: all 0.2s ease;
  box-shadow: var(--shadow-sm);
}

.copy-bubble::before {
  content: '';
  position: absolute;
  bottom: -4px;
  left: 50%;
  transform: translateX(-50%);
  border-top: 4px solid var(--text-primary);
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
}

.code-copy-container:hover .copy-bubble {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.copy-bubble.copied {
  background-color: var(--color-success);
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.copy-bubble.copied::before {
  border-top-color: var(--color-success);
}

/* Stats view */
.card-stats {
  display: flex;
  background-color: var(--bg-hover);
  border-radius: var(--radius-md);
  padding: 0.75rem;
  text-align: center;
}

.stat-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.stat-box:first-child {
  border-right: 1px solid var(--border-color);
}

.stat-val {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
  font-family: ui-monospace, monospace;
}

.stat-label {
  font-size: 0.7rem;
  color: var(--text-muted);
}

/* Textbook tags list styling */
.card-textbooks {
  font-size: 0.775rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-height: 48px;
}

.textbooks-title {
  color: var(--text-muted);
  font-weight: 500;
}

.textbooks-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.tb-tag {
  background-color: rgba(79, 70, 229, 0.05);
  color: var(--color-accent);
  border: 1px solid rgba(79, 70, 229, 0.15);
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
  max-width: 140px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.empty-textbooks {
  color: var(--text-muted);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 0.5rem;
}

.card-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-top: auto;
}

.manage-btn {
  flex-grow: 1;
  padding: 0.5rem;
  font-size: 0.825rem;
}

.btn-disband {
  background: none;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-disband:hover {
  background-color: var(--color-danger-bg);
  border-color: rgba(220, 38, 38, 0.3);
  color: var(--color-danger);
}

/* Empty State */
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

/* Modals overlays */
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
}

.close-btn {
  background: none;
  border: none;
  font-size: 0.9rem;
  cursor: pointer;
  opacity: 0.6;
}

.close-btn:hover {
  opacity: 1;
}

.modal-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 0.5rem;
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
}

.confirm-actions .btn {
  padding: 0.5rem 1.25rem;
}

/* Alert styles */
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

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
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
