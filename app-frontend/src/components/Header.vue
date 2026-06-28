<template>
  <header class="header glass-panel">
    <!-- Left: Page Title / Breadcrumbs -->
    <div class="header-left">
      <div class="breadcrumb">
        <span class="root-node">SmartEdu Portal</span>
        <span class="separator">/</span>
        <span class="current-node">{{ pageTitle }}</span>
      </div>
    </div>

    <!-- Right: Notification Center & Info -->
    <div class="header-right">
      <!-- Notification Dropdown Toggle -->
      <div class="notification-wrapper" v-click-outside="closeNotifications">
        <button class="notification-trigger" @click="toggleNotifications">
          <span class="bell-icon"><i class="ph ph-bell"></i></span>
          <span class="badge badge-danger unread-count" v-if="unreadCount > 0">
            {{ unreadCount }}
          </span>
        </button>

        <!-- Dropdown Panel -->
        <transition name="slide-up">
          <div class="notification-dropdown glass-panel" v-if="showNotifications">
            <div class="dropdown-header">
              <h3>站内通知</h3>
              <button class="btn-text" @click="markAllAsRead" v-if="unreadCount > 0">
                全部已读
              </button>
            </div>
            
            <div class="notification-list" v-if="notifications.length > 0">
              <div 
                v-for="notif in notifications" 
                :key="notif.id" 
                class="notification-item"
                :class="{ unread: !notif.is_read }"
                @click="markAsRead(notif)"
              >
                <div class="notif-header">
                  <span class="notif-title">{{ notif.title }}</span>
                  <span class="notif-time">{{ formatTime(notif.created_at) }}</span>
                </div>
                <p class="notif-content">{{ notif.content }}</p>
                <div class="notif-actions">
                  <span class="unread-dot" v-if="!notif.is_read"></span>
                  <button class="btn-delete" @click.stop="deleteNotification(notif.id)">删除</button>
                </div>
              </div>
            </div>

            <div class="empty-notifications" v-else>
              <div class="empty-icon"><i class="ph ph-mailbox"></i></div>
              <p>暂无新通知</p>
            </div>
          </div>
        </transition>
      </div>

      <!-- Quick User Action or System Time -->
      <div class="system-time">
        <span class="time-label">系统时间:</span>
        <span class="time-value">{{ formattedTime }}</span>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../store/auth'
import { api } from '../utils/api'

const route = useRoute()
const authStore = useAuthStore()

const showNotifications = ref(false)
const systemTime = ref(new Date())

// Notifications state
const notifications = ref([
  {
    id: 1,
    title: '系统欢迎信',
    content: '欢迎进入智能教育平台。在这里，教师可上传教材进行 RAG 分析，学生可进行互动问答。',
    is_read: false,
    created_at: new Date(Date.now() - 3600000).toISOString()
  },
  {
    id: 2,
    title: '新功能上线',
    content: 'AI 问答模块已支持流式输出，问答体验更加丝滑，欢迎体验。',
    is_read: true,
    created_at: new Date(Date.now() - 86400000).toISOString()
  }
])

const unreadCount = computed(() => {
  return notifications.value.filter(n => !n.is_read).length
})

const pageTitle = computed(() => {
  const path = route.path
  if (path.startsWith('/student/chat')) return 'AI 问答书库'
  if (path.startsWith('/student')) return '我的班级'
  if (path.startsWith('/teacher/textbooks')) return '教材知识库'
  if (path.startsWith('/teacher/audit')) return '学生会话审计'
  if (path.startsWith('/teacher/class')) return '班级管理'
  if (path.startsWith('/teacher')) return '班级工作台'
  if (path.startsWith('/admin/content')) return '内容审计'
  if (path.startsWith('/admin/config')) return '系统配置'
  if (path.startsWith('/admin')) return '用户管理'
  return '控制台'
})

const toggleNotifications = () => {
  showNotifications.value = !showNotifications.value
  if (showNotifications.value) {
    fetchNotifications()
  }
}

const closeNotifications = () => {
  showNotifications.value = false
}

const fetchNotifications = async () => {
  if (!authStore.isAuthenticated) {
    notifications.value = []
    return
  }

  try {
    const res = await api.get('/notifications')
    notifications.value = res
  } catch (err) {
    console.warn('Backend API connection offline, using simulated notifications.')
  }
}

const markAsRead = async (notif) => {
  if (!notif.is_read) {
    notif.is_read = true
    if (authStore.isAuthenticated) {
      try {
        await api.post(`/notifications/${notif.id}/read`)
      } catch (err) {
        console.error('Failed to mark notification as read on backend:', err)
      }
    }
  }
}

const markAllAsRead = async () => {
  notifications.value.forEach(n => n.is_read = true)
  if (authStore.isAuthenticated) {
    try {
      await api.post('/notifications/read-all')
    } catch (err) {
      console.error('Failed to mark all notifications as read on backend:', err)
    }
  }
}

const deleteNotification = async (id) => {
  notifications.value = notifications.value.filter(n => n.id !== id)
  if (authStore.isAuthenticated) {
    try {
      await api.delete(`/notifications/${id}`)
    } catch (err) {
      console.error('Failed to delete notification on backend:', err)
    }
  }
}

const formatTime = (timeStr) => {
  const date = new Date(timeStr)
  return `${date.getMonth() + 1}-${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

// Timer for system time
let timerInterval
onMounted(() => {
  timerInterval = setInterval(() => {
    systemTime.value = new Date()
  }, 1000)
  
  fetchNotifications()
  
  // Poll notifications every 30s in live mode
  setInterval(() => {
    if (authStore.isAuthenticated) {
      fetchNotifications()
    }
  }, 30000)
})

watch(() => authStore.token, () => {
  fetchNotifications()
})

onUnmounted(() => {
  clearInterval(timerInterval)
})

const formattedTime = computed(() => {
  const d = systemTime.value
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
})

// 简单的自定义 click-outside 指令模拟助手
const vClickOutside = {
  mounted(el, binding) {
    el.clickOutsideEvent = function(event) {
      if (!(el === event.target || el.contains(event.target))) {
        binding.value(event)
      }
    }
    document.body.addEventListener('click', el.clickOutsideEvent)
  },
  unmounted(el) {
    document.body.removeEventListener('click', el.clickOutsideEvent)
  }
}
</script>

<style scoped>
.header {
  height: 70px;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2rem;
  border-bottom: 1px solid var(--border-color);
  background-color: rgba(255, 255, 255, 0.8);
  position: sticky;
  top: 0;
  z-index: 90;
}

.header-left {
  display: flex;
  align-items: center;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.root-node {
  color: var(--text-muted);
  font-weight: 500;
}

.separator {
  color: var(--border-color);
}

.current-node {
  color: var(--text-primary);
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.notification-wrapper {
  position: relative;
}

.notification-trigger {
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s ease;
}

.notification-trigger:hover {
  background-color: var(--bg-hover);
}

.unread-count {
  position: absolute;
  top: 2px;
  right: 2px;
  font-size: 0.65rem;
  padding: 0.2rem 0.4rem;
  border-radius: 9999px;
}

.notification-dropdown {
  position: absolute;
  right: 0;
  top: 50px;
  width: 340px;
  max-height: 460px;
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  z-index: 100;
}

.dropdown-header {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: rgba(255, 255, 255, 0.9);
}

.dropdown-header h3 {
  font-size: 0.95rem;
  font-weight: 600;
}

.btn-text {
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
}

.btn-text:hover {
  color: var(--color-primary-hover);
  text-decoration: underline;
}

.notification-list {
  overflow-y: auto;
  flex-grow: 1;
  background-color: rgba(255, 255, 255, 0.7);
}

.notification-item {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  transition: background-color 0.2s ease;
  position: relative;
}

.notification-item:hover {
  background-color: var(--bg-hover);
}

.notification-item.unread {
  background-color: rgba(37, 99, 235, 0.02);
}

.notif-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.25rem;
  gap: 0.5rem;
}

.notif-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}

.notif-time {
  font-size: 0.7rem;
  color: var(--text-muted);
  white-space: nowrap;
}

.notif-content {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.4;
  margin-bottom: 0.5rem;
}

.notif-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.unread-dot {
  width: 6px;
  height: 6px;
  background-color: var(--color-primary);
  border-radius: 50%;
}

.btn-delete {
  background: none;
  border: none;
  color: var(--color-danger);
  font-size: 0.7rem;
  cursor: pointer;
  margin-left: auto;
  opacity: 0.6;
}

.btn-delete:hover {
  opacity: 1;
  text-decoration: underline;
}

.empty-notifications {
  padding: 3rem 1.5rem;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-muted);
  background-color: rgba(255, 255, 255, 0.7);
}

.empty-icon {
  font-size: 2.25rem;
}

.empty-notifications p {
  font-size: 0.85rem;
}

.system-time {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.8rem;
  border-left: 1px solid var(--border-color);
  padding-left: 1.25rem;
}

.time-label {
  color: var(--text-muted);
}

.time-value {
  color: var(--text-secondary);
  font-family: ui-monospace, monospace;
}

/* Animations */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(10px);
  opacity: 0;
}

/* Mock Toggle Capsule Button */
.mock-toggle-btn {
  border: 1px solid var(--border-color);
  padding: 0.4rem 0.8rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  user-select: none;
  background-color: var(--bg-hover);
  color: var(--text-secondary);
}

.mock-toggle-btn.mock-active {
  background-color: var(--color-warning-bg);
  color: var(--color-warning);
  border-color: rgba(217, 119, 6, 0.2);
}

.mock-toggle-btn.mock-active:hover {
  background-color: #fef3c7;
  border-color: var(--color-warning);
}

.mock-toggle-btn.mock-inactive {
  background-color: var(--color-success-bg);
  color: var(--color-success);
  border-color: rgba(5, 150, 105, 0.2);
}

.mock-toggle-btn.mock-inactive:hover {
  background-color: #d1fae5;
  border-color: var(--color-success);
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background-color: var(--color-success);
  border-radius: 50%;
  display: inline-block;
  animation: pulse 1.8s infinite;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(5, 150, 105, 0.4); }
  70% { box-shadow: 0 0 0 6px rgba(5, 150, 105, 0); }
  100% { box-shadow: 0 0 0 0 rgba(5, 150, 105, 0); }
}
</style>
