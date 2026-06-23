<template>
  <div class="audit-container">
    <!-- Left Sidebar: Student Session List -->
    <div class="sessions-sidebar glass-panel animate-fade">
      <div class="sidebar-header">
        <h3>学生提问会话</h3>
        <p class="sidebar-subtitle">点击调阅学生问答详情与 AI 学情诊断</p>
        
        <!-- Filters panel -->
        <div class="filter-controls">
          <select v-model="selectedClassId" class="form-control filter-select" @change="handleFilterChange">
            <option value="">-- 所有班级 --</option>
            <option v-for="c in classes" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </div>
      </div>

      <div class="session-list" v-if="filteredSessions.length > 0">
        <div 
          v-for="session in filteredSessions" 
          :key="session.id" 
          class="session-item"
          :class="{ active: activeSessionId === session.id }"
          @click="selectSession(session.id)"
        >
          <span class="chat-icon"><i class="ph ph-magnifying-glass"></i></span>
          <div class="session-info">
            <div class="session-meta">
              <span class="student-name"><i class="ph ph-user"></i> {{ session.student_name }}</span>
              <span class="class-tag">{{ session.class_name }}</span>
            </div>
            <span class="session-title" :title="session.title">{{ session.title }}</span>
            <span class="session-date">{{ formatTime(session.created_at) }}</span>
          </div>
        </div>
      </div>
      
      <div class="empty-sessions" v-else>
        <span class="empty-icon"><i class="ph ph-chat-slash"></i></span>
        <p>暂无符合筛选条件的学生会话</p>
      </div>
    </div>

    <!-- Right Workspace: dialogue auditing -->
    <div class="chat-workspace glass-panel">
      <!-- Active Session Audit Panel -->
      <template v-if="activeSessionId && activeSession">
        <!-- Dialog Header -->
        <div class="workspace-header">
          <div class="active-title-area">
            <div class="student-profile">
              <div class="avatar">{{ activeSession.student_name[0]?.toUpperCase() }}</div>
              <div>
                <h3>{{ activeSession.student_name }} 的对话记录</h3>
                <span class="session-detail-meta">
                  班级: {{ activeSession.class_name }} | 教材: <i class="ph ph-book"></i> {{ activeSession.textbook_title }}
                </span>
              </div>
            </div>
          </div>
          <span class="badge badge-success">只读审计模式</span>
        </div>

        <!-- Highlight Permanent Learning Summary Panel at the Top of dialogue pane -->
        <div class="summary-highlight-panel">
          <div class="summary-banner alert-success">
            <div class="summary-banner-header">
              <span class="summary-label"><i class="ph ph-lightbulb"></i> AI 阶段性学情诊断摘要</span>
              <span class="summary-time" v-if="activeSession.summary_updated_at">
                更新于: {{ formatTime(activeSession.summary_updated_at) }}
              </span>
            </div>
            <p class="summary-text">
              {{ activeSession.summary || 'AI 诊断引擎正在评估本场对话，当对话轮数达到触发条件时，将自动在此输出学情总结。' }}
            </p>
          </div>
        </div>

        <!-- Readonly Messages Viewport -->
        <div class="messages-viewport" ref="viewport">
          <div class="message-list">
            <div 
              v-for="msg in messages" 
              :key="msg.id" 
              class="message-wrapper"
              :class="msg.sender"
            >
              <!-- Sender Avatar -->
              <div class="message-avatar">
                <i :class="msg.sender === 'user' ? 'ph ph-student' : msg.sender === 'ai' ? 'ph ph-cpu' : 'ph ph-wrench'"></i>
              </div>

              <!-- Bubble Content -->
              <div class="message-bubble">
                <div class="bubble-content">
                  <div v-html="renderMarkdown(msg.content)"></div>
                </div>
                <span class="message-time">{{ formatTime(msg.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- Empty Workspace State -->
      <div class="empty-workspace animate-fade" v-else>
        <div class="empty-illustration"><i class="ph ph-magnifying-glass"></i></div>
        <h2>选择一个会话开展学情监督</h2>
        <p>在左侧列表中，调阅学生在各个班级关联教材下的 AI 对话记录，掌握真实学情，检查 AI 输出的学术合理性。</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { api } from '../../utils/api'
import { renderMarkdown } from '../../utils/markdown'

// Audit states
const sessions = ref([])
const activeSessionId = ref(null)
const messages = ref([])
const selectedClassId = ref('')

const loading = ref(false)
const viewport = ref(null)

const classes = ref([])

// Filtered list
const filteredSessions = computed(() => {
  if (!selectedClassId.value) return sessions.value
  return sessions.value.filter(s => s.class_id === parseInt(selectedClassId.value))
})

const activeSession = computed(() => {
  return sessions.value.find(s => s.id === activeSessionId.value) || null
})

// Load Teacher Audit Sessions
const fetchAuditSessions = async () => {
  loading.value = true
  try {
    const res = await api.get('/chat/teacher/student-chats')
    sessions.value = res
  } catch (error) {
    console.error('Failed to fetch student chats:', error)
    sessions.value = []
  } finally {
    loading.value = false
  }
}

// Fetch teacher classes for sidebar filtering
const fetchTeacherClasses = async () => {
  try {
    const res = await api.get('/classes/dashboard')
    classes.value = (res.classes || []).map(c => ({
      id: c.id,
      name: c.name
    }))
  } catch (error) {
    console.error('Failed to load teacher classes for audit:', error)
    classes.value = []
  }
}

onMounted(() => {
  fetchAuditSessions()
  fetchTeacherClasses()
})

const selectSession = async (id) => {
  activeSessionId.value = id
  
  try {
    const res = await api.get(`/chat/teacher/student-chats/${id}/messages`)
    messages.value = res
  } catch (error) {
    alert(error.message || '获取审计对话消息失败。')
    messages.value = []
  }
  
  scrollToBottom()
}

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  return `${date.getMonth() + 1}-${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

const scrollToBottom = () => {
  nextTick(() => {
    if (viewport.value) {
      viewport.value.scrollTop = viewport.value.scrollHeight
    }
  })
}
</script>

<style scoped>
.audit-container {
  display: flex;
  height: calc(100vh - 110px);
  width: 100%;
  gap: 1.5rem;
}

/* Sidebar styling */
.sessions-sidebar {
  width: 290px;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-color);
  background-color: rgba(255, 255, 255, 0.7);
  border-radius: var(--radius-lg);
  overflow: hidden;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 1.25rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.sidebar-header h3 {
  font-size: 0.95rem;
  font-weight: 700;
}

.sidebar-subtitle {
  font-size: 0.725rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.filter-controls {
  margin-top: 0.25rem;
}

.filter-select {
  padding: 0.45rem 0.75rem;
  font-size: 0.8rem;
  height: 36px;
}

.session-list {
  flex-grow: 1;
  overflow-y: auto;
  padding: 0.75rem 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s ease;
}

.session-item:hover {
  background-color: var(--bg-hover);
}

.session-item.active {
  background-color: rgba(37, 99, 235, 0.06);
  color: var(--color-primary);
}

.chat-icon {
  font-size: 1rem;
}

.session-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex-grow: 1;
  gap: 0.15rem;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}

.student-name {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.class-tag {
  font-size: 0.65rem;
  background-color: var(--bg-hover);
  padding: 1px 4px;
  border-radius: 4px;
  color: var(--color-primary);
  max-width: 80px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-title {
  font-size: 0.825rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-primary);
}

.session-date {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.empty-sessions {
  padding: 3rem 1rem;
  text-align: center;
  color: var(--text-muted);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.empty-icon {
  font-size: 2.25rem;
}

.empty-sessions p {
  font-size: 0.75rem;
  line-height: 1.4;
}

/* Chat Workspace */
.chat-workspace {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-color);
  background-color: #ffffff;
  border-radius: var(--radius-lg);
  overflow: hidden;
  min-width: 0;
}

.workspace-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.student-profile {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.student-profile .avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
}

.student-profile h3 {
  font-size: 1rem;
  font-weight: 600;
}

.session-detail-meta {
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* Highlighter learning summary panel at the top of dialogue area */
.summary-highlight-panel {
  padding: 1.25rem 1.5rem 0.25rem;
}

.summary-banner {
  padding: 1rem 1.25rem;
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  box-shadow: var(--shadow-sm);
  border: 1px solid rgba(5, 150, 105, 0.15);
  background: linear-gradient(135deg, #ecfdf5, #f0fdf4);
}

.summary-banner-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
}

.summary-label {
  font-weight: 700;
  color: var(--color-success);
}

.summary-time {
  color: var(--text-muted);
}

.summary-text {
  color: var(--text-secondary);
  line-height: 1.5;
  font-weight: 500;
}

/* Messages viewport */
.messages-viewport {
  flex-grow: 1;
  overflow-y: auto;
  padding: 1.5rem;
  background-color: var(--bg-base);
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.message-wrapper {
  display: flex;
  gap: 0.75rem;
  max-width: 80%;
}

.message-wrapper.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-wrapper.ai {
  align-self: flex-start;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background-color: #ffffff;
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  box-shadow: var(--shadow-sm);
  flex-shrink: 0;
}

.message-bubble {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.bubble-content {
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  line-height: 1.5;
  word-break: break-word;
  box-shadow: var(--shadow-sm);
  white-space: pre-wrap;
}

.user .bubble-content {
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: #ffffff;
  border-top-right-radius: 2px;
}

.user .message-time {
  text-align: right;
}

.ai .bubble-content {
  background-color: #f1f5f9; /* Flat warm/soft gray */
  color: var(--text-primary);
  border-top-left-radius: 2px;
  border: 1px solid #e2e8f0;
}

.message-time {
  font-size: 0.675rem;
  color: var(--text-muted);
  padding: 0 0.25rem;
}

/* Empty State */
.empty-workspace {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
  gap: 1rem;
}

.empty-illustration {
  font-size: 4rem;
}

.empty-workspace h2 {
  font-size: 1.25rem;
  color: var(--text-primary);
  font-weight: 600;
}

.empty-workspace p {
  font-size: 0.85rem;
  max-width: 440px;
  line-height: 1.5;
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
</style>
