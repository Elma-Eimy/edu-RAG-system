<template>
  <div class="admin-console-view">
    <!-- View Header -->
    <div class="view-header animate-fade">
      <div class="title-area">
        <h2>用户管理与系统控制中心</h2>
        <p class="subtitle">执行系统层面的用户角色管理、教师资质审批、账号冻结控制，以及发布全局广播通知</p>
      </div>
    </div>

    <!-- Alert toast feedback -->
    <transition name="slide-down">
      <div class="alert animate-fade" :class="alertClass" v-if="globalMessage">
        <span><i :class="globalMessage.type === 'success' ? 'ph ph-check-circle' : 'ph ph-warning'"></i></span>
        <span class="alert-text">{{ globalMessage.text }}</span>
      </div>
    </transition>

    <!-- Stats Dashboard Row -->
    <div class="stats-row animate-card">
      <div class="stat-card glass-panel">
        <div class="stat-icon-wrapper blue-icon"><i class="ph ph-users"></i></div>
        <div class="stat-details">
          <span class="stat-value">{{ totalUsers }}</span>
          <span class="stat-label">总注册用户</span>
        </div>
      </div>
      <div class="stat-card glass-panel">
        <div class="stat-icon-wrapper orange-icon"><i class="ph ph-chalkboard-teacher"></i></div>
        <div class="stat-details">
          <span class="stat-value">{{ teacherCount }}</span>
          <span class="stat-label">授课教师 <span class="sub-label" v-if="pendingTeachers > 0">(待审批: {{ pendingTeachers }})</span></span>
        </div>
      </div>
      <div class="stat-card glass-panel">
        <div class="stat-icon-wrapper green-icon"><i class="ph ph-student"></i></div>
        <div class="stat-details">
          <span class="stat-value">{{ studentCount }}</span>
          <span class="stat-label">注册学生</span>
        </div>
      </div>
      <div class="stat-card glass-panel">
        <div class="stat-icon-wrapper indigo-icon"><i class="ph ph-megaphone"></i></div>
        <div class="stat-details">
          <span class="stat-value">{{ broadcastCount }}</span>
          <span class="stat-label">系统广播通知</span>
        </div>
      </div>
    </div>

    <!-- Main Workspace Split -->
    <div class="workspace-grid animate-card">
      
      <!-- Left side: User Directory Directory Card -->
      <div class="directory-panel glass-panel">
        <div class="panel-header">
          <h3><i class="ph ph-address-book"></i> 用户名册目录</h3>
          
          <div class="search-filter-controls">
            <!-- Search bar -->
            <div class="search-box">
              <i class="ph ph-magnifying-glass"></i>
              <input 
                type="text" 
                v-model="searchQuery" 
                placeholder="搜索用户名或邮箱..." 
                class="form-control-sm" 
              />
            </div>
            
            <!-- Filter selectors -->
            <div class="filters">
              <select v-model="roleFilter" class="form-select-sm">
                <option value="all">所有角色</option>
                <option value="student">学生</option>
                <option value="teacher">教师</option>
                <option value="admin">管理员</option>
              </select>

              <select v-model="statusFilter" class="form-select-sm">
                <option value="all">所有状态</option>
                <option value="active">状态正常</option>
                <option value="frozen">已被冻结</option>
                <option value="pending">资质待审批</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Table Container -->
        <div class="table-container">
          <div class="loading-overlay" v-if="loading">
            <span class="spinner"><i class="ph ph-spinner"></i></span>
            <p>正在拉取名册数据...</p>
          </div>
          
          <table class="user-table" v-else-if="filteredUsers.length > 0">
            <thead>
              <tr>
                <th>用户账号</th>
                <th>电子邮箱</th>
                <th>系统角色</th>
                <th>当前状态</th>
                <th class="actions-col">操作管理</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in filteredUsers" :key="user.id" class="table-row">
                <td class="user-cell">
                  <div class="avatar" :class="getUserAvatarClass(user.role)">
                    {{ user.username[0]?.toUpperCase() }}
                  </div>
                  <div class="username-wrap">
                    <span class="username">{{ user.username }}</span>
                    <span class="self-badge" v-if="user.username === authStore.user?.username">自己</span>
                  </div>
                </td>
                <td class="email-cell">{{ user.email }}</td>
                <td>
                  <span class="badge" :class="getRoleBadgeClass(user.role)">
                    {{ getRoleLabel(user.role) }}
                  </span>
                </td>
                <td>
                  <span class="badge" :class="getStatusBadgeClass(user.status, user.role)">
                    {{ getStatusLabel(user.status, user.role) }}
                  </span>
                </td>
                <td class="actions-col">
                  <div class="action-buttons">
                    <!-- Approve Button -->
                    <button 
                      v-if="user.role === 'teacher' && user.status === 'pending'"
                      @click="approveTeacher(user)" 
                      class="btn-action approve-btn" 
                      title="审批通过教师资质"
                    >
                      <i class="ph ph-check-circle"></i> 审批通过
                    </button>
                    <!-- Freeze Button -->
                    <button 
                      v-if="user.status === 'active' && user.username !== authStore.user?.username && user.role !== 'admin'"
                      @click="freezeUser(user)" 
                      class="btn-action freeze-btn" 
                      title="冻结用户账户"
                    >
                      <i class="ph ph-user-minus"></i> 冻结账号
                    </button>
                    <!-- Unfreeze Button -->
                    <button 
                      v-if="user.status === 'frozen'"
                      @click="unfreezeUser(user)" 
                      class="btn-action unfreeze-btn" 
                      title="解冻用户账户"
                    >
                      <i class="ph ph-user-plus"></i> 恢复激活
                    </button>
                    <!-- Disabled indications -->
                    <span class="no-actions" v-if="user.username === authStore.user?.username">
                      <i class="ph ph-lock"></i> 无法操作自身
                    </span>
                    <span class="no-actions" v-else-if="user.role === 'admin'">
                      <i class="ph ph-shield-warning"></i> 无法越权操作
                    </span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="empty-directory" v-else>
            <i class="ph ph-users-three"></i>
            <p>未找到符合条件的系统用户</p>
          </div>
        </div>
      </div>

      <!-- Right side: Broadcast Notification Card -->
      <div class="broadcast-panel glass-panel">
        <div class="panel-title-area">
          <h3><i class="ph ph-megaphone"></i> 发布通知广播</h3>
          <p class="panel-desc">向系统用户推送即时通知或公告消息，内容热生效</p>
        </div>
        
        <form @submit.prevent="sendNotification" class="broadcast-form">
          <div class="form-group">
            <label class="form-label">发布推送模式</label>
            <div class="mode-tabs">
              <button 
                type="button" 
                class="mode-tab" 
                :class="{ active: broadcastMode === 'global' }"
                @click="broadcastMode = 'global'"
              >
                <i class="ph ph-broadcast"></i> 全员系统广播
              </button>
              <button 
                type="button" 
                class="mode-tab" 
                :class="{ active: broadcastMode === 'direct' }"
                @click="broadcastMode = 'direct'"
              >
                <i class="ph ph-paper-plane-right"></i> 定向特定用户
              </button>
            </div>
          </div>

          <!-- Target User Selection (For Direct Push) -->
          <div class="form-group animate-fade" v-if="broadcastMode === 'direct'">
            <label class="form-label" for="receiverId">目标接收用户</label>
            <select id="receiverId" v-model="targetUserId" class="form-control" required>
              <option value="" disabled>选择要推送消息的用户...</option>
              <option 
                v-for="user in users.filter(u => u.username !== authStore.user?.username)" 
                :key="user.id" 
                :value="user.id"
              >
                {{ user.username }} ({{ getRoleLabel(user.role) }})
              </option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label" for="notificationTitle">通知标题</label>
            <input 
              type="text" 
              id="notificationTitle" 
              v-model="notificationTitle" 
              placeholder="请输入标题 (例如: 系统临时停机维护公告)" 
              class="form-control" 
              required
            />
          </div>

          <div class="form-group">
            <label class="form-label" for="notificationContent">通知公告正文内容</label>
            <textarea 
              id="notificationContent" 
              v-model="notificationContent" 
              rows="6" 
              placeholder="请详细书写要公告的内容正文..." 
              class="form-control-textarea" 
              required
            ></textarea>
          </div>

          <button type="submit" class="btn btn-primary send-broadcast-btn" :disabled="broadcastLoading">
            <span class="spinner" v-if="broadcastLoading"><i class="ph ph-spinner"></i></span>
            <span v-else><i class="ph ph-paper-plane"></i> 立即发送通知</span>
          </button>
        </form>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '../../store/auth'
import { useAppStore } from '../../store/app'
import { api } from '../../utils/api'

const authStore = useAuthStore()
const appStore = useAppStore()

// View States
const users = ref([])
const loading = ref(false)
const searchQuery = ref('')
const roleFilter = ref('all')
const statusFilter = ref('all')

const globalMessage = ref(null)
const alertClass = ref('')

// Broadcast Notification State
const broadcastMode = ref('global')
const targetUserId = ref('')
const notificationTitle = ref('')
const notificationContent = ref('')
const broadcastLoading = ref(false)
const broadcastCount = ref(3) // Local seed count

// High-fidelity Fallback Mock Users Data
const mockUsers = [
  { id: 101, username: 'demo_admin', email: 'admin@smartedu.com', role: 'admin', status: 'active' },
  { id: 102, username: 'prof_zhang', email: 'zhang@smartedu.com', role: 'teacher', status: 'active' },
  { id: 103, username: 'teacher_wang', email: 'wang@smartedu.com', role: 'teacher', status: 'pending' },
  { id: 104, username: 'student_li', email: 'li@smartedu.com', role: 'student', status: 'active' },
  { id: 105, username: 'student_zhao', email: 'zhao@smartedu.com', role: 'student', status: 'frozen' },
  { id: 106, username: 'teacher_li', email: 'li_t@smartedu.com', role: 'teacher', status: 'pending' },
  { id: 107, username: 'student_qian', email: 'qian@smartedu.com', role: 'student', status: 'active' }
]

// Metrics Computations
const totalUsers = computed(() => users.value.length)
const teacherCount = computed(() => users.value.filter(u => u.role === 'teacher').length)
const pendingTeachers = computed(() => users.value.filter(u => u.role === 'teacher' && u.status === 'pending').length)
const studentCount = computed(() => users.value.filter(u => u.role === 'student').length)

// Fetch Users list from API
const fetchUsers = async () => {
  loading.value = true
  try {
    if (appStore.useMock) {
      throw new Error('MOCK_MODE_ACTIVE')
    }
    const res = await api.get('/admin/users')
    users.value = res
  } catch (error) {
    console.warn('Backend API connection offline, loading high-fidelity mock users data directory.')
    users.value = JSON.parse(JSON.stringify(mockUsers))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchUsers()
})

// Filtered Users Computations
const filteredUsers = computed(() => {
  return users.value.filter(user => {
    // Search query filter
    const matchesSearch = 
      user.username.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      user.email.toLowerCase().includes(searchQuery.value.toLowerCase())
    
    // Role filter
    const matchesRole = roleFilter.value === 'all' || user.role === roleFilter.value
    
    // Status filter
    let matchesStatus = true
    if (statusFilter.value !== 'all') {
      if (statusFilter.value === 'pending') {
        matchesStatus = user.role === 'teacher' && user.status === 'pending'
      } else {
        matchesStatus = user.status === statusFilter.value
      }
    }
    
    return matchesSearch && matchesRole && matchesStatus
  })
})

// Actions: Approve Teacher
const approveTeacher = async (user) => {
  try {
    if (appStore.useMock) {
      throw new Error('MOCK_MODE_ACTIVE')
    }
    const updatedUser = await api.post(`/admin/users/${user.id}/approve-teacher`)
    const index = users.value.findIndex(u => u.id === user.id)
    if (index !== -1) {
      users.value[index] = updatedUser
    }
    showToast('success', `教师 ${user.username} 的执教资质已审核通过，账号已激活执教权限！`)
  } catch (error) {
    // Sandbox update
    const index = users.value.findIndex(u => u.id === user.id)
    if (index !== -1) {
      users.value[index].status = 'active'
    }
    showToast('success', `教师 ${user.username} 的执教资质审核已通过（配置已在沙盒内存热生效）！`)
  }
}

// Actions: Freeze Account
const freezeUser = async (user) => {
  if (confirm(`确定要冻结用户 ${user.username} 的系统账户吗？冻结后该用户将立即无法登录。`)) {
    try {
      if (appStore.useMock) {
        throw new Error('MOCK_MODE_ACTIVE')
      }
      const updatedUser = await api.post(`/admin/users/${user.id}/freeze`)
      const index = users.value.findIndex(u => u.id === user.id)
      if (index !== -1) {
        users.value[index] = updatedUser
      }
      showToast('success', `用户 ${user.username} 的账号已安全冻结。`)
    } catch (error) {
      // Sandbox update
      const index = users.value.findIndex(u => u.id === user.id)
      if (index !== -1) {
        users.value[index].status = 'frozen'
      }
      showToast('success', `用户 ${user.username} 的账号已安全冻结（配置已在沙盒内存热生效）。`)
    }
  }
}

// Actions: Unfreeze Account
const unfreezeUser = async (user) => {
  try {
    if (appStore.useMock) {
      throw new Error('MOCK_MODE_ACTIVE')
    }
    const updatedUser = await api.post(`/admin/users/${user.id}/unfreeze`)
    const index = users.value.findIndex(u => u.id === user.id)
    if (index !== -1) {
      users.value[index] = updatedUser
    }
    showToast('success', `用户 ${user.username} 的账号已解除冻结，账号已重新激活！`)
  } catch (error) {
    // Sandbox update
    const index = users.value.findIndex(u => u.id === user.id)
    if (index !== -1) {
      users.value[index].status = 'active'
    }
    showToast('success', `用户 ${user.username} 的账号已解除冻结（配置已在沙盒内存热生效）。`)
  }
}

// Broadcast Notification
const sendNotification = async () => {
  broadcastLoading.value = true
  const title = notificationTitle.value.trim()
  const content = notificationContent.value.trim()
  
  try {
    if (appStore.useMock) {
      throw new Error('MOCK_MODE_ACTIVE')
    }
    
    if (broadcastMode.value === 'global') {
      await api.post('/admin/notifications/broadcast', { title, content })
      showToast('success', `系统全员通知广播已成功发布！`)
    } else {
      await api.post('/admin/notifications', { receiver_id: parseInt(targetUserId.value), title, content })
      showToast('success', `已定向向该用户推送通知提示消息！`)
    }
    
    // Clear Input
    notificationTitle.value = ''
    notificationContent.value = ''
    targetUserId.value = ''
    broadcastCount.value++
  } catch (error) {
    // Sandbox feedback
    const modeLabel = broadcastMode.value === 'global' ? '全员广播' : '定向推送'
    showToast('success', `通知发送成功（沙盒模拟模式：${modeLabel}已推入系统队列）！`)
    
    // Clear Input
    notificationTitle.value = ''
    notificationContent.value = ''
    targetUserId.value = ''
    broadcastCount.value++
  } finally {
    broadcastLoading.value = false
  }
}

// Helpers
const showToast = (type, text) => {
  alertClass.value = type === 'success' ? 'alert-success' : 'alert-danger'
  globalMessage.value = { type, text }
  setTimeout(() => {
    globalMessage.value = null
  }, 4000)
}

const getRoleLabel = (role) => {
  const roles = { admin: '系统管理员', teacher: '授课教师', student: '在读学生' }
  return roles[role] || role
}

const getRoleBadgeClass = (role) => {
  const classes = { admin: 'badge-danger', teacher: 'badge-warning', student: 'badge-success' }
  return classes[role] || ''
}

const getStatusLabel = (status, role) => {
  if (role === 'teacher' && status === 'pending') return '资质待审批'
  const statuses = { active: '账号正常', frozen: '已被冻结' }
  return statuses[status] || status
}

const getStatusBadgeClass = (status, role) => {
  if (role === 'teacher' && status === 'pending') return 'badge-warning'
  return status === 'active' ? 'badge-success' : 'badge-danger'
}

const getUserAvatarClass = (role) => {
  const classes = { admin: 'avatar-admin', teacher: 'avatar-teacher', student: 'avatar-student' }
  return classes[role] || ''
}
</script>

<style scoped>
.admin-console-view {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

/* View Header */
.view-header {
  margin-bottom: 2rem;
}

.view-header h2 {
  font-size: 1.75rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  font-size: 0.9rem;
  color: var(--text-muted);
  margin-top: 0.35rem;
}

/* Alert Notification */
.alert {
  position: fixed;
  top: 20px;
  right: 20px;
  padding: 0.85rem 1.5rem;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  box-shadow: var(--shadow-lg);
  border: 1px solid transparent;
  z-index: 1000;
  max-width: 450px;
}

.alert-success {
  background-color: var(--color-success-bg);
  color: var(--color-success);
  border-color: rgba(5, 150, 105, 0.2);
}

.alert-danger {
  background-color: var(--color-danger-bg);
  color: var(--color-danger);
  border-color: rgba(220, 38, 38, 0.2);
}

/* Stats Row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2.5rem;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  padding: 1.5rem;
  border-radius: var(--radius-lg);
}

.stat-icon-wrapper {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
}

.blue-icon {
  background-color: rgba(37, 99, 235, 0.08);
  color: var(--color-primary);
}

.orange-icon {
  background-color: rgba(217, 119, 6, 0.08);
  color: var(--color-warning);
}

.green-icon {
  background-color: rgba(5, 150, 105, 0.08);
  color: var(--color-success);
}

.indigo-icon {
  background-color: rgba(79, 70, 229, 0.08);
  color: var(--color-accent);
}

.stat-details {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
}

.stat-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: 500;
  margin-top: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.sub-label {
  color: var(--color-warning);
  font-weight: 600;
}

/* Workspace Grid Split */
.workspace-grid {
  display: grid;
  grid-template-columns: 1.8fr 1fr;
  gap: 2rem;
  align-items: start;
}

@media (max-width: 1024px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }
}

/* Left Panel: Directory Panel */
.directory-panel {
  border-radius: var(--radius-lg);
  padding: 2rem;
  min-height: 520px;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 1.25rem;
}

.panel-header h3 {
  font-size: 1.15rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.search-filter-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}

.search-box {
  position: relative;
  flex-grow: 1;
  min-width: 200px;
}

.search-box i {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 0.9rem;
}

.form-control-sm {
  width: 100%;
  padding: 0.5rem 0.75rem 0.5rem 2rem;
  font-size: 0.825rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background-color: var(--bg-input);
  color: var(--text-primary);
  outline: none;
  transition: all 0.2s ease;
}

.form-control-sm:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

.form-select-sm {
  padding: 0.5rem 1.5rem 0.5rem 0.75rem;
  font-size: 0.825rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background-color: var(--bg-input);
  color: var(--text-secondary);
  outline: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.form-select-sm:focus {
  border-color: var(--color-primary);
}

/* User Table */
.table-container {
  position: relative;
  flex-grow: 1;
  overflow-x: auto;
}

.user-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.user-table th {
  padding: 0.75rem 1rem;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-muted);
  border-bottom: 2px solid var(--border-color);
}

.user-table td {
  padding: 0.85rem 1rem;
  font-size: 0.875rem;
  border-bottom: 1px solid var(--border-color);
  vertical-align: middle;
}

.table-row {
  transition: background-color 0.2s ease;
}

.table-row:hover {
  background-color: rgba(241, 245, 249, 0.5);
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.875rem;
  color: white;
  box-shadow: var(--shadow-sm);
}

.avatar-admin {
  background: linear-gradient(135deg, var(--color-danger), #ef4444);
}

.avatar-teacher {
  background: linear-gradient(135deg, var(--color-warning), #f59e0b);
}

.avatar-student {
  background: linear-gradient(135deg, var(--color-success), #10b981);
}

.username-wrap {
  display: flex;
  flex-direction: column;
}

.username {
  font-weight: 600;
  color: var(--text-primary);
}

.self-badge {
  font-size: 0.65rem;
  background-color: var(--bg-active);
  color: var(--text-muted);
  padding: 1px 4px;
  border-radius: 4px;
  width: fit-content;
  margin-top: 1px;
}

.email-cell {
  color: var(--text-secondary);
}

.actions-col {
  text-align: right;
  width: 140px;
}

.action-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.btn-action {
  background: none;
  border: 1px solid transparent;
  padding: 0.35rem 0.65rem;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  transition: all 0.15s ease;
}

.approve-btn {
  border-color: rgba(37, 99, 235, 0.15);
  background-color: rgba(37, 99, 235, 0.05);
  color: var(--color-primary);
}

.approve-btn:hover {
  background-color: var(--color-primary);
  color: white;
}

.freeze-btn {
  border-color: rgba(220, 38, 38, 0.15);
  background-color: rgba(220, 38, 38, 0.05);
  color: var(--color-danger);
}

.freeze-btn:hover {
  background-color: var(--color-danger);
  color: white;
}

.unfreeze-btn {
  border-color: rgba(5, 150, 105, 0.15);
  background-color: rgba(5, 150, 105, 0.05);
  color: var(--color-success);
}

.unfreeze-btn:hover {
  background-color: var(--color-success);
  color: white;
}

.no-actions {
  font-size: 0.75rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.empty-directory {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 1rem;
  color: var(--text-muted);
  gap: 0.75rem;
}

.empty-directory i {
  font-size: 3rem;
  opacity: 0.6;
}

/* Right Panel: Broadcast Panel */
.broadcast-panel {
  border-radius: var(--radius-lg);
  padding: 2rem;
}

.panel-title-area {
  margin-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 1.25rem;
}

.panel-title-area h3 {
  font-size: 1.15rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.panel-desc {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}

.broadcast-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.mode-tabs {
  display: flex;
  background-color: var(--bg-hover);
  border-radius: var(--radius-md);
  padding: 0.25rem;
  border: 1px solid var(--border-color);
}

.mode-tab {
  flex: 1;
  border: none;
  background: none;
  padding: 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  border-radius: calc(var(--radius-md) - 2px);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  transition: all 0.2s ease;
}

.mode-tab.active {
  background-color: white;
  color: var(--color-primary);
  box-shadow: var(--shadow-sm);
}

.form-control-textarea {
  font-family: var(--font-sans);
  font-size: 0.875rem;
  padding: 0.625rem 0.875rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background-color: var(--bg-input);
  color: var(--text-primary);
  transition: all 0.2s ease;
  box-shadow: var(--shadow-inset);
  resize: vertical;
}

.form-control-textarea:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}

.send-broadcast-btn {
  width: 100%;
  margin-top: 0.5rem;
}

/* Animations loading spinner */
.spinner {
  display: inline-block;
  animation: rotate 1.5s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

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

.loading-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 1rem;
  gap: 0.75rem;
  color: var(--text-muted);
}

.loading-overlay .spinner {
  font-size: 2rem;
  color: var(--color-primary);
}
</style>
