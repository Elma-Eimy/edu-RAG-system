<template>
  <div class="chat-container">
    <!-- Feedback alert banner -->
    <transition name="slide-down">
      <div class="alert" :class="alertClass" v-if="globalMessage">
        <span><i :class="globalMessage.type === 'success' ? 'ph ph-check-circle' : 'ph ph-warning'"></i></span>
        {{ globalMessage.text }}
      </div>
    </transition>

    <!-- Left Sidebar: Session List -->
    <div class="sessions-sidebar glass-panel animate-fade">
      <div class="sidebar-header">
        <h3>对话历史</h3>
        <button class="btn btn-primary new-chat-btn" @click="openNewChatModal" :disabled="loading">
          <span><i class="ph ph-plus"></i></span> 新建对话
        </button>
      </div>

      <div class="session-list" v-if="sessions.length > 0">
        <div 
          v-for="session in sessions" 
          :key="session.id" 
          class="session-item"
          :class="{ active: activeSessionId === session.id }"
          @click="selectSession(session.id)"
        >
          <span class="chat-icon"><i class="ph ph-chat-circle"></i></span>
          <div class="session-info">
            <span class="session-title" :title="session.title">{{ session.title }}</span>
            <span class="session-date">{{ formatTime(session.created_at) }}</span>
          </div>
          <button class="delete-session-btn" @click.stop="confirmDeleteSession(session)" title="删除对话">
            <i class="ph ph-trash"></i>
          </button>
        </div>
      </div>
      
      <div class="empty-sessions" v-else>
        <span class="empty-icon"><i class="ph ph-chat-slash"></i></span>
        <p>暂无对话历史，请新建会话开始学习</p>
      </div>
    </div>

    <!-- Right Panels: Active Chat Workspace -->
    <div class="chat-workspace glass-panel">
      <!-- Chat Workspace Header -->
      <div class="workspace-header" v-if="activeSession">
        <div class="active-title-area">
          <h3>{{ activeSession.title }}</h3>
          <div class="associated-textbook">
            <span class="textbook-icon"><i class="ph ph-book-open"></i></span>
            <span class="textbook-name">关联教材: {{ activeTextbookName }}</span>
          </div>
        </div>
        <button class="btn btn-secondary clear-chat-btn" @click="confirmDeleteSession(activeSession)">
          <i class="ph ph-trash"></i> 清理会话
        </button>
      </div>

      <!-- Messages Viewport -->
      <div class="messages-viewport" ref="viewport" v-if="activeSessionId">
        <div class="message-list">
          <div 
            v-for="msg in messages" 
            :key="msg.id" 
            class="message-wrapper animate-message"
            :class="msg.sender"
          >
            <!-- Sender Avatar -->
            <div class="message-avatar">
              <i :class="msg.sender === 'user' ? 'ph ph-student' : msg.sender === 'ai' ? 'ph ph-cpu' : 'ph ph-wrench'"></i>
            </div>

            <!-- Bubble Content -->
            <div class="message-bubble">
              <!-- 深度思考模块：只在有推理思考内容时显示，允许展开与折叠 -->
              <div class="thinking-box" v-if="msg.reasoning_content">
                <div class="thinking-header" @click="msg.showThinking = !msg.showThinking">
                  <span class="thinking-title">
                    <i class="ph ph-brain"></i>
                    {{ msg.isThinking ? '正在思考中...' : '已完成思考' }}
                  </span>
                  <span class="toggle-icon">
                    <i :class="msg.showThinking ? 'ph ph-caret-up' : 'ph ph-caret-down'"></i>
                  </span>
                </div>
                <div class="thinking-content" v-if="msg.showThinking">
                  {{ msg.reasoning_content }}
                </div>
              </div>

              <!-- 回答正文：普通消息、流式输出、或等待大模型返回时展示等待动画 -->
              <div class="bubble-content" v-if="msg.content || (msg.isStreaming && !msg.reasoning_content)">
                <div v-if="msg.isStreaming && !msg.content && !msg.reasoning_content" class="typing-indicator">
                  <span class="dot"></span>
                  <span class="dot"></span>
                  <span class="dot"></span>
                </div>
                <div v-else>
                  <div v-html="renderMarkdown(msg.content)"></div>
                  <!-- 流式输出光标：仅在 AI 正在生成正文时展示 -->
                  <span class="streaming-cursor" v-if="msg.isStreaming"></span>
                </div>
              </div>
              <span class="message-time">{{ formatTime(msg.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty Workspace State -->
      <div class="empty-workspace animate-fade" v-else>
        <div class="empty-illustration"><i class="ph ph-robot"></i></div>
        <h2>欢迎来到 AI 智能问答书库</h2>
        <p>选择或新建一个对话，绑定教材后，即可开启由向量数据库（ChromaDB）支撑的 RAG 检索增强学习。</p>
        <button class="btn btn-primary" @click="openNewChatModal">开始交互式学习</button>
      </div>

      <!-- Input control drawer -->
      <div class="input-panel" v-if="activeSessionId">
        <!-- 思考模式控制栏：可切换是否启用 DeepSeek-R1 思考链 -->
        <div class="input-options-bar">
          <label class="toggle-option-label">
            <input 
              type="checkbox" 
              v-model="useReasoning" 
              :disabled="streaming"
              class="toggle-checkbox"
            />
            <span class="toggle-text">
              <i class="ph ph-brain"></i> 深度思考模式 (DeepSeek-R1)
            </span>
          </label>
        </div>

        <form @submit.prevent="handleSendMessage" class="input-form">
          <textarea 
            v-model="inputText" 
            class="form-control text-input" 
            placeholder="输入您的问题（例如：什么是向量空间？）" 
            required
            rows="2"
            @keydown.enter.prevent="handleEnterKey"
            :disabled="streaming"
          ></textarea>
          
          <button type="submit" class="btn btn-primary send-btn" :disabled="streaming || !inputText.trim()">
            <span v-if="streaming">生成中...</span>
            <span v-else><i class="ph ph-paper-plane-right"></i> 发送</span>
          </button>
        </form>
        <span class="input-tip">提示：按 Enter 键快速发送问题，按 Shift + Enter 键换行。</span>
      </div>
    </div>

    <!-- Create New Chat Modal (Glassmorphic Selection) -->
    <transition name="fade">
      <div class="modal-overlay" v-if="showNewChatModal" @click.self="closeNewChatModal">
        <div class="modal-card glass-panel animate-zoom">
          <div class="modal-header">
            <h3>开启新对话</h3>
            <button class="close-btn" @click="closeNewChatModal"><i class="ph ph-x"></i></button>
          </div>

          <!-- Modal Error Banner -->
          <transition name="slide-down">
            <div class="alert alert-danger modal-alert" v-if="modalError">
              <span><i class="ph ph-warning"></i></span> {{ modalError }}
            </div>
          </transition>

          <form @submit.prevent="handleCreateSession" class="modal-form">
            <div class="form-group">
              <label class="form-label" for="chatTitle">对话主题</label>
              <input 
                type="text" 
                id="chatTitle" 
                v-model="newChatTitle" 
                class="form-control" 
                placeholder="请输入对话主题或首个问题" 
                required
                :disabled="modalLoading"
              />
            </div>

            <div class="form-group">
              <label class="form-label" for="textbookSelect">选择关联教材</label>
              <select 
                id="textbookSelect" 
                v-model="selectedTextbookId" 
                class="form-control" 
                required
                :disabled="modalLoading"
              >
                <option value="" disabled selected>-- 请选择绑定的教材 --</option>
                <option 
                  v-for="tb in availableTextbooks" 
                  :key="tb.id" 
                  :value="tb.id"
                >
                  <i class="ph ph-book"></i> {{ tb.title }}{{ tb.className ? ' (班级: ' + tb.className + ')' : '' }}
                </option>
              </select>
              <span class="input-helper">只有您已加入的班级所绑定的教材，才可在此进行提问。</span>
            </div>

            <div class="modal-actions">
              <button type="button" class="btn btn-secondary" @click="closeNewChatModal" :disabled="modalLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary submit-btn" :disabled="modalLoading">
                <span class="spinner" v-if="modalLoading"><i class="ph ph-spinner"></i></span>
                <span v-else>立即新建</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </transition>

    <!-- Delete Confirmation Modal -->
    <transition name="fade">
      <div class="modal-overlay confirm-overlay" v-if="showConfirmDelete" @click.self="closeConfirmDelete">
        <div class="modal-card confirm-card glass-panel animate-zoom">
          <h3>删除会话</h3>
          <p class="confirm-message">
            确认要永久删除对话 <strong>“{{ sessionToDelete?.title }}”</strong> 吗？删除后此历史记录将不可恢复。
          </p>
          <div class="confirm-actions">
            <button class="btn btn-secondary" @click="closeConfirmDelete">取消</button>
            <button class="btn class-danger btn-danger" @click="handleDeleteSession">确认删除</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { api } from '../../utils/api'
import { useAppStore } from '../../store/app'
import { renderMarkdown } from '../../utils/markdown'

const appStore = useAppStore()

// Sessions & Messages State
const sessions = ref([])
const activeSessionId = ref(null)
const messages = ref([])

const showNewChatModal = ref(false)
const showConfirmDelete = ref(false)
const sessionToDelete = ref(null)

// Form Fields
const newChatTitle = ref('')
const selectedTextbookId = ref('')
const inputText = ref('')
// 新增：深度思考模式开关状态
const useReasoning = ref(false)

const loading = ref(false)
const streaming = ref(false)
const modalLoading = ref(false)
const modalError = ref('')
const globalMessage = ref(null)
const viewport = ref(null)

const availableTextbooks = ref([])

// Computed Properties
const activeSession = computed(() => {
  return sessions.value.find(s => s.id === activeSessionId.value) || null
})

const activeTextbookName = computed(() => {
  if (!activeSession.value) return ''
  const tb = availableTextbooks.value.find(t => t.id === activeSession.value.textbook_id)
  return tb ? tb.title : `未知教材 (ID: ${activeSession.value.textbook_id})`
})

const alertClass = computed(() => {
  if (!globalMessage.value) return ''
  return globalMessage.value.type === 'success' ? 'alert-success' : 'alert-danger'
})

const showErrorToast = (text) => {
  globalMessage.value = { type: 'error', text }
  setTimeout(() => {
    globalMessage.value = null
  }, 4000)
}

const showSuccessToast = (text) => {
  globalMessage.value = { type: 'success', text }
  setTimeout(() => {
    globalMessage.value = null
  }, 4000)
}

// Load session details
const loadSessions = async () => {
  loading.value = true
  try {
    const res = await api.get('/chat/sessions')
    sessions.value = res
  } catch (error) {
    showErrorToast(error.message || '获取会话列表失败。')
    sessions.value = []
  } finally {
    loading.value = false
  }
}

const loadMessages = async (sessionId) => {
  try {
    const res = await api.get(`/chat/sessions/${sessionId}/messages`)
    // 初始化历史消息的折叠状态：默认不展开历史思考链路
    messages.value = res.map(msg => ({
      ...msg,
      showThinking: false,
      isThinking: false
    }))
  } catch (error) {
    showErrorToast(error.message || '获取历史消息失败。')
    messages.value = []
  }
  scrollToBottom()
}

const loadTextbooks = async () => {
  try {
    const res = await api.get('/textbooks')
    availableTextbooks.value = res
  } catch (error) {
    showErrorToast(error.message || '获取授权教材列表失败。')
    availableTextbooks.value = []
  }
}

onMounted(() => {
  loadSessions()
  loadTextbooks()
})

const selectSession = (id) => {
  activeSessionId.value = id
  loadMessages(id)
}

// Format date helper
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  return `${date.getMonth() + 1}-${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

// Scroll viewport dynamically
const scrollToBottom = () => {
  nextTick(() => {
    if (viewport.value) {
      viewport.value.scrollTop = viewport.value.scrollHeight
    }
  })
}

// Watch active messages array length to automatically adjust scrolling
watch(() => messages.value.length, () => {
  scrollToBottom()
})

// Modal control
const openNewChatModal = () => {
  newChatTitle.value = ''
  selectedTextbookId.value = ''
  modalError.value = ''
  showNewChatModal.value = true
}

const closeNewChatModal = () => {
  showNewChatModal.value = false
}

// Create new session logic
const handleCreateSession = async () => {
  modalLoading.value = true
  modalError.value = ''

  const sessionData = {
    title: newChatTitle.value.trim(),
    textbook_id: parseInt(selectedTextbookId.value)
  }

  try {
    const newSession = await api.post('/chat/sessions', sessionData)
    sessions.value.unshift(newSession)
    selectSession(newSession.id)
    closeNewChatModal()
  } catch (error) {
    modalError.value = error.message || '新建会话失败，请重试。'
  } finally {
    modalLoading.value = false
  }
}

// Client-side typewriter stream smoothing queue
let typewriterQueue = ''
let typewriterInterval = null

const startTypewriter = (msg) => {
  if (typewriterInterval) clearInterval(typewriterInterval)
  
  typewriterInterval = setInterval(() => {
    if (typewriterQueue.length > 0) {
      // 动态吞吐速率，防止在长网络延迟后爆字堆积
      const charsToTake = typewriterQueue.length > 35 ? 5 : typewriterQueue.length > 10 ? 2 : 1
      const chunk = typewriterQueue.slice(0, charsToTake)
      typewriterQueue = typewriterQueue.slice(charsToTake)
      msg.content += chunk
      scrollToBottom()
    } else if (!msg.isStreaming) {
      clearInterval(typewriterInterval)
      typewriterInterval = null
    }
  }, 20) // 20ms 频率刷新字符，提供绝对丝滑手感
}

onUnmounted(() => {
  if (typewriterInterval) clearInterval(typewriterInterval)
})

// Send Message handler (SSE native stream reader)
const handleSendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || streaming.value) return

  inputText.value = ''
  
  // Append User message
  const userMsg = {
    id: Date.now(),
    sender: 'user',
    content: text,
    created_at: new Date().toISOString()
  }
  messages.value.push(userMsg)
  
  streaming.value = true
  
  // Append a placeholder AI message for streaming
  // 新增：增加推理内容字段、正在思考状态，且默认展开思考内容面板
  const aiMsg = {
    id: Date.now() + 1,
    sender: 'ai',
    content: '',
    reasoning_content: '',
    isThinking: useReasoning.value,
    showThinking: true,
    created_at: new Date().toISOString(),
    isStreaming: true
  }
  messages.value.push(aiMsg)
  
  // 获取推入数组后的响应式代理对象，确保属性修改能触发 Vue 视图更新
  const reactiveAiMsg = messages.value[messages.value.length - 1]

  typewriterQueue = ''
  startTypewriter(reactiveAiMsg)

  try {
    // Try actual SSE connection over fetch ReadableStream
    const response = await fetch(`${api.baseUrl}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({
        session_id: activeSessionId.value,
        content: text,
        // 新增：向后端传递是否启用思考模式的参数
        reasoning: useReasoning.value
      })
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.msg || err.detail || '会话异常，无权使用当前教材进行对话。')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      
      buffer = lines.pop() // keep partial line in buffer

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue
        
        if (trimmed.startsWith('data: ')) {
          const dataStr = trimmed.slice(6)
          if (dataStr === '[DONE]') {
            break
          }
          
          try {
            const parsed = JSON.parse(dataStr)
            
            // 1. 如果是推理/思考内容，追加到推理字段，并维持 isThinking 为 true
            if (parsed.reasoning) {
              reactiveAiMsg.isThinking = true
              reactiveAiMsg.reasoning_content += parsed.reasoning
              scrollToBottom()
            } 
            // 2. 如果是正文内容，追加到 typewriterQueue 进行平滑输出，并将 isThinking 标记为 false（思考完毕）
            else if (parsed.content) {
              reactiveAiMsg.isThinking = false
              typewriterQueue += parsed.content
            } else if (parsed.error) {
              throw new Error(parsed.error)
            }
          } catch (e) {
            console.error('Failed parsing SSE:', dataStr)
          }
        }
      }
    }
  } catch (error) {
    if (!reactiveAiMsg.content && !reactiveAiMsg.reasoning_content) {
      messages.value = messages.value.filter(m => m.id !== reactiveAiMsg.id)
    }
    showErrorToast(error.message || '发送消息失败，请检查网络或后端状态。')
  }

  reactiveAiMsg.isStreaming = false
  streaming.value = false
}

// Enter Key shorthand trigger
const handleEnterKey = (e) => {
  if (streaming.value) return
  handleSendMessage()
}

// Delete session controls
const confirmDeleteSession = (session) => {
  sessionToDelete.value = session
  showConfirmDelete.value = true
}

const closeConfirmDelete = () => {
  showConfirmDelete.value = false
  sessionToDelete.value = null
}

const handleDeleteSession = async () => {
  if (!sessionToDelete.value) return
  const id = sessionToDelete.value.id

  try {
    await api.delete(`/chat/sessions/${id}`)
  } catch (error) {
    console.warn('Backend API connection offline, deleting session locally.')
  }

  sessions.value = sessions.value.filter(s => s.id !== id)
  if (activeSessionId.value === id) {
    activeSessionId.value = null
    messages.value = []
  }
  closeConfirmDelete()
}
</script>

<style scoped>
.chat-container {
  display: flex;
  height: calc(100vh - 110px); /* Adjust to viewport inside unified shell */
  width: 100%;
  gap: 1.5rem;
}

/* Sidebar Styling */
.sessions-sidebar {
  width: 280px;
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
  color: var(--text-primary);
}

.new-chat-btn {
  width: 100%;
  padding: 0.5rem;
  font-size: 0.85rem;
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
  padding: 0.65rem 0.75rem;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  group: true;
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

.delete-session-btn {
  background: none;
  border: none;
  font-size: 0.8rem;
  cursor: pointer;
  padding: 0.2rem;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.session-item:hover .delete-session-btn {
  opacity: 0.6;
}

.delete-session-btn:hover {
  opacity: 1 !important;
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

.active-title-area h3 {
  font-size: 1.1rem;
  font-weight: 600;
}

.associated-textbook {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.textbook-name {
  font-weight: 500;
  color: var(--text-secondary);
}

.clear-chat-btn {
  padding: 0.45rem 0.75rem;
  font-size: 0.75rem;
}

/* Messages Viewport */
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

/* User Message styling: royal gradient */
.user .bubble-content {
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: #ffffff;
  border-top-right-radius: 2px;
}

.user .message-time {
  text-align: right;
}

/* AI Message styling: flat slate-gray as requested */
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

/* Blinking typewriter cursor */
.streaming-cursor {
  display: inline-block;
  width: 2px;
  height: 1.1em;
  background-color: var(--color-primary);
  margin-left: 2px;
  vertical-align: middle;
  animation: blink 0.8s step-end infinite;
}

@keyframes blink {
  from, to { background-color: transparent; }
  50% { background-color: var(--color-primary); }
}

/* Empty Workspace State styling */
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
  margin-bottom: 0.5rem;
}

/* Input panel control styling */
.input-panel {
  padding: 1.25rem 1.5rem;
  border-top: 1px solid var(--border-color);
  background-color: #ffffff;
}

.input-form {
  display: flex;
  gap: 0.75rem;
  align-items: flex-end;
}

.text-input {
  flex-grow: 1;
  resize: none;
  padding: 0.625rem 0.875rem;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  line-height: 1.4;
  height: 52px;
}

.send-btn {
  padding: 0.75rem 1.5rem;
  font-size: 0.875rem;
  height: 52px;
  flex-shrink: 0;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.12);
}

.send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.input-tip {
  font-size: 0.7rem;
  color: var(--text-muted);
  display: block;
  margin-top: 0.35rem;
}

/* Modal overlays styles */
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

/* Delete confirm */
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

/* Spinner */
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

.animate-message {
  animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(8px);
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
    transform: scale(0.96);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

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

/* Toast alert style */
.alert {
  position: absolute;
  top: 1rem;
  left: 50%;
  transform: translateX(-50%);
  padding: 0.75rem 1.25rem;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  box-shadow: var(--shadow-md);
  border: 1px solid transparent;
  z-index: 10000;
  min-width: 300px;
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

/* ==========================================================================
   深度思考模式 (DeepSeek-R1) 专属组件样式 (使用 Phosphor Icons)
   ========================================================================== */

/* 思考盒子外层容器 */
.thinking-box {
  background-color: #f8fafc;
  border-left: 3px solid var(--color-primary);
  border-radius: var(--radius-sm);
  margin-bottom: 0.75rem;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  border-top: 1px solid #e2e8f0;
  border-right: 1px solid #e2e8f0;
  border-bottom: 1px solid #e2e8f0;
  width: 100%;
}

/* 思考控制栏头部 */
.thinking-header {
  padding: 0.65rem 0.875rem;
  background-color: #f1f5f9;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s ease;
}

.thinking-header:hover {
  background-color: #e2e8f0;
}

/* 思考栏标题与脑图图标 */
.thinking-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.thinking-title i {
  color: var(--color-primary);
  font-size: 1rem;
}

/* 折叠展开指示角标 */
.toggle-icon i {
  font-size: 0.85rem;
  color: var(--text-muted);
}

/* 思考内容主体：使用等宽字体呈现推导过程 */
.thinking-content {
  padding: 0.75rem 0.875rem;
  font-size: 0.8rem;
  color: var(--text-muted);
  line-height: 1.6;
  white-space: pre-wrap;
  border-top: 1px solid #e2e8f0;
  background-color: #fafafa;
  font-family: Consolas, Monaco, monospace;
}

/* 输入框上方的思考模式选项切换栏 */
.input-options-bar {
  display: flex;
  align-items: center;
  padding-bottom: 0.5rem;
  margin-bottom: 0.5rem;
  border-bottom: 1px dashed var(--border-color);
}

.toggle-option-label {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  cursor: pointer;
  user-select: none;
}

.toggle-checkbox {
  width: 15px;
  height: 15px;
  cursor: pointer;
}

/* 开关文本与脑图图标 */
.toggle-text {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 0.25rem;
  transition: color 0.2s ease;
}

.toggle-checkbox:checked + .toggle-text {
  color: var(--color-primary);
  font-weight: 600;
}

.toggle-text i {
  font-size: 0.95rem;
  color: var(--color-primary);
}

/* Typing Indicator Animation */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  min-height: 20px;
}

.typing-indicator .dot {
  width: 6px;
  height: 6px;
  background-color: var(--text-muted);
  border-radius: 50%;
  opacity: 0.4;
  animation: bounce 1.4s infinite both;
}

.typing-indicator .dot:nth-child(1) {
  animation-delay: 0s;
}

.typing-indicator .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  40% {
    transform: scale(1.15);
    opacity: 0.85;
  }
}
</style>
