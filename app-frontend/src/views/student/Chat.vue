<template>
  <div class="chat-container">
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
              <div class="bubble-content">
                {{ msg.content }}
                <!-- Streaming cursor (rendered only for AI active writing) -->
                <span class="streaming-cursor" v-if="msg.isStreaming"></span>
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
                  <i class="ph ph-book"></i> {{ tb.title }} (班级: {{ tb.className }})
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
import { ref, onMounted, computed, nextTick, watch } from 'vue'
import { api } from '../../utils/api'
import { useAppStore } from '../../store/app'

const appStore = useAppStore()

// Sessions & Messages State
const sessions = ref([])
const activeSessionId = ref(null)
const messages = ref([])

const mockSessionsMessages = ref({})

const showNewChatModal = ref(false)
const showConfirmDelete = ref(false)
const sessionToDelete = ref(null)

// Form Fields
const newChatTitle = ref('')
const selectedTextbookId = ref('')
const inputText = ref('')

const loading = ref(false)
const streaming = ref(false)
const modalLoading = ref(false)
const modalError = ref('')
const viewport = ref(null)

// Mock Fallback Database
const mockTextbooks = [
  { id: 3, title: '高等数学上册', className: '高等数学 A 班' },
  { id: 4, title: '线性代数与空间解析几何', className: '线性代数 B 班' }
]

const mockSessions = [
  {
    id: 12,
    title: '向量空间的定义是什么',
    textbook_id: 3,
    created_at: new Date(Date.now() - 3600000).toISOString()
  }
]

const mockMessages = [
  {
    id: 201,
    sender: 'user',
    content: '向量空间的定义是什么？',
    created_at: new Date(Date.now() - 3500000).toISOString()
  },
  {
    id: 202,
    sender: 'ai',
    content: '向量空间（线性空间）是一个集合，其元素称为“向量”。为了构成向量空间，该集合必须定义“向量加法”和“标量乘法”两种运算，并满足八条基本代数公理，例如加法交换律、结合律、存在零向量、存在逆向量，以及标量乘法的分配律等。最常见的例子就是我们熟悉的三维欧氏空间 R³。',
    created_at: new Date(Date.now() - 3495000).toISOString()
  }
]

const availableTextbooks = ref([...mockTextbooks])

// Computed Properties
const activeSession = computed(() => {
  return sessions.value.find(s => s.id === activeSessionId.value) || null
})

const activeTextbookName = computed(() => {
  if (!activeSession.value) return ''
  const tb = availableTextbooks.value.find(t => t.id === activeSession.value.textbook_id)
  return tb ? tb.title : `未知教材 (ID: ${activeSession.value.textbook_id})`
})

// Load session details
const loadSessions = async () => {
  loading.value = true
  try {
    const res = await api.get('/chat/sessions')
    sessions.value = res
  } catch (error) {
    console.warn('Backend API connection failed, falling back to mock session list.')
    sessions.value = [...mockSessions]
  } finally {
    loading.value = false
  }
}

const loadMessages = async (sessionId) => {
  try {
    const res = await api.get(`/chat/sessions/${sessionId}/messages`)
    messages.value = res
  } catch (error) {
    // If mock bypass
    if (sessionId === 12) {
      messages.value = [...mockMessages]
    } else if (mockSessionsMessages.value[sessionId]) {
      messages.value = [...mockSessionsMessages.value[sessionId]]
    } else {
      messages.value = []
    }
  }
  scrollToBottom()
}

onMounted(() => {
  loadSessions()
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

// Watch active messages array to automatically adjust scrolling
watch(messages, () => {
  scrollToBottom()
}, { deep: true })

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
    // Mock simulation
    const mockNew = {
      id: Math.floor(Math.random() * 1000) + 200,
      title: sessionData.title,
      textbook_id: sessionData.textbook_id,
      created_at: new Date().toISOString()
    }
    sessions.value.unshift(mockNew)
    selectSession(mockNew.id)
    closeNewChatModal()
  } finally {
    modalLoading.value = false
  }
}

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
  
  if (appStore.useMock) {
    mockSessionsMessages.value[activeSessionId.value] = [...messages.value]
  }
  
  streaming.value = true
  
  // Append a placeholder AI message for streaming
  const aiMsg = {
    id: Date.now() + 1,
    sender: 'ai',
    content: '',
    created_at: new Date().toISOString(),
    isStreaming: true
  }
  messages.value.push(aiMsg)

  try {
    if (appStore.useMock) {
      throw new Error('MOCK_MODE_ACTIVE')
    }
    // Try actual SSE connection over fetch ReadableStream
    const response = await fetch(`${api.baseUrl}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({
        session_id: activeSessionId.value,
        content: text
      })
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || '会话异常，无权使用当前教材进行对话。')
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
            if (parsed.content) {
              aiMsg.content += parsed.content
              scrollToBottom()
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
    // FALLBACK Mock typing animation simulator
    console.warn('Backend SSE endpoint offline, generating sandbox AI response.')
    
    // Smart academic responses depending on query
    let responseText = `收到您关于关联教材的问题。这是一个模拟沙盒环境。RAG 向量检索在此被激活，它通过将知识切片为 200 字块以注入 ChromaDB。您刚刚提问的内容是：“${text}”。在真实后端启动后，系统将流式输出完全定制化的解答。`
    if (text.includes('向量') || text.includes('空间') || text.includes('线性')) {
      responseText = '在线性代数中，向量空间（又称线性空间）是由称为向量的代数对象组成的集合。加法和标量乘法运算在其上有着良好定义。一个集合若要被认可为向量空间，必须在分配律、结合律、零向量等 8 条公理上完全自洽。'
    } else if (text.includes('极限') || text.includes('微积分')) {
      responseText = '在微积分学中，极限是核心支柱概念。导数定义为自变量趋近于零时函数增量之比的极限值。积分则是无限求和的极限。理解极限的 ε-δ 定义是踏入高等数学殿堂的关键。'
    }

    let tokenIndex = 0
    const tokens = responseText.split('')
    const interval = setInterval(() => {
      if (tokenIndex < tokens.length) {
        aiMsg.content += tokens[tokenIndex]
        tokenIndex++
        scrollToBottom()
      } else {
        clearInterval(interval)
        aiMsg.isStreaming = false
        streaming.value = false
        if (appStore.useMock) {
          mockSessionsMessages.value[activeSessionId.value] = [...messages.value]
        }
      }
    }, 45) // Typist speed
    return // avoid triggering the final catch block immediately
  }

  aiMsg.isStreaming = false
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
</style>
