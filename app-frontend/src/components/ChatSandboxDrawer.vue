<template>
  <!-- Chat Test Sandbox Drawer (Sliding from Right) -->
  <transition name="slide-left">
    <div class="test-drawer-overlay" v-if="show" @click.self="emitClose">
      <div class="test-drawer glass-panel animate-slide-left">
        <div class="drawer-header">
          <div class="drawer-title-area">
            <h3>教材调试沙盒</h3>
            <p class="drawer-subtitle">
              <i class="ph ph-book-open"></i> 当前调试教材: {{ textbook?.title }}
            </p>
          </div>
          <button class="close-btn" @click="emitClose"><i class="ph ph-x"></i></button>
        </div>

        <!-- Messages Viewport -->
        <div class="drawer-messages-viewport" ref="drawerViewport">
          <div class="drawer-message-list" v-if="testMessages.length > 0">
            <div 
              v-for="msg in testMessages" 
              :key="msg.id" 
              class="message-wrapper animate-message"
              :class="msg.sender"
            >
              <div class="message-avatar">
                <i :class="msg.sender === 'user' ? 'ph ph-student' : 'ph ph-cpu'"></i>
              </div>
              <div class="message-bubble">
                <div class="bubble-content">
                  <div v-if="msg.isStreaming && !msg.content" class="typing-indicator">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                  </div>
                  <div v-else>
                    <div v-html="renderMarkdown(msg.content)"></div>
                    <span class="streaming-cursor" v-if="msg.isStreaming"></span>
                  </div>
                </div>
                <span class="message-time">{{ formatTime(msg.created_at) }}</span>
              </div>
            </div>
          </div>
          <div class="drawer-empty-state" v-else>
            <div class="empty-icon"><i class="ph ph-sparkles"></i></div>
            <h4>进入教材 AI 问答调试模式</h4>
            <p>系统已基于此教材的切片向量（ChromaDB）和全文检索（SQLite FTS5）建立混合检索索引。在此提问可以检验 RAG 检索质量与 AI 回复效果。</p>
          </div>
        </div>

        <!-- Input area -->
        <div class="drawer-input-panel">
          <form @submit.prevent="handleSendTestMessage" class="drawer-input-form">
            <textarea 
              v-model="testInputText" 
              class="form-control text-input" 
              placeholder="输入测试问题（例如：书里是怎么定义这个概念的？）" 
              required
              rows="2"
              @keydown.enter.prevent="handleEnterKeyInTest"
              :disabled="testStreaming"
            ></textarea>
            <button type="submit" class="btn btn-primary send-btn" :disabled="testStreaming || !testInputText.trim()">
              <span v-if="testStreaming">生成中...</span>
              <span v-else><i class="ph ph-paper-plane-right"></i> 发送</span>
            </button>
          </form>
          <div class="drawer-input-actions" v-if="testMessages.length > 0">
            <button type="button" class="btn-clear-session" @click="handleClearTestSession" :disabled="testStreaming">
              <i class="ph ph-trash"></i> 清空当前对话历史
            </button>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { api } from '../utils/api'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps({
  show: {
    type: Boolean,
    required: true
  },
  textbook: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close'])

const testActiveSessionId = ref(null)
const testMessages = ref([])
const testInputText = ref('')
const testStreaming = ref(false)
const drawerViewport = ref(null)

const emitClose = () => {
  if (testStreaming.value) return
  emit('close')
}

// Format ISO time to HH:MM
const formatTime = (isoString) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

// Scroll viewport to bottom
const scrollDrawerToBottom = () => {
  nextTick(() => {
    if (drawerViewport.value) {
      drawerViewport.value.scrollTop = drawerViewport.value.scrollHeight
    }
  })
}

// Initialize session for testing
const initSession = async () => {
  if (!props.textbook) return
  testMessages.value = []
  testInputText.value = ''
  testActiveSessionId.value = null

  try {
    const sessionsList = await api.get('/chat/sessions')
    const existingSession = sessionsList.find(s => s.textbook_id === props.textbook.id)

    if (existingSession) {
      testActiveSessionId.value = existingSession.id
      const msgs = await api.get(`/chat/sessions/${existingSession.id}/messages`)
      testMessages.value = msgs
    } else {
      const newSess = await api.post('/chat/sessions', {
        title: `调试 - ${props.textbook.title}`,
        textbook_id: props.textbook.id
      })
      testActiveSessionId.value = newSess.id
      testMessages.value = []
    }
    scrollDrawerToBottom()
  } catch (error) {
    console.error('Failed to init test sandbox session:', error)
  }
}

// Reset session state
const resetSession = () => {
  testMessages.value = []
  testInputText.value = ''
  testActiveSessionId.value = null
  testStreaming.value = false
}

// Watchers
watch(() => props.show, async (newVal) => {
  if (newVal) {
    await initSession()
  } else {
    resetSession()
  }
})

// 客户端打字机效果流式平滑处理队列
let typewriterQueue = ''
let typewriterInterval = null

const startTypewriter = (msg) => {
  if (typewriterInterval) clearInterval(typewriterInterval)
  
  typewriterInterval = setInterval(() => {
    if (typewriterQueue.length > 0) {
      const charsToTake = typewriterQueue.length > 35 ? 5 : typewriterQueue.length > 10 ? 2 : 1
      const chunk = typewriterQueue.slice(0, charsToTake)
      typewriterQueue = typewriterQueue.slice(charsToTake)
      msg.content += chunk
      scrollDrawerToBottom()
    } else if (!msg.isStreaming) {
      clearInterval(typewriterInterval)
      typewriterInterval = null
    }
  }, 20)
}

onUnmounted(() => {
  if (typewriterInterval) clearInterval(typewriterInterval)
})

// Send test message
const handleSendTestMessage = async () => {
  const text = testInputText.value.trim()
  if (!text || testStreaming.value || !testActiveSessionId.value) return

  testInputText.value = ''

  const userMsg = {
    id: Date.now(),
    sender: 'user',
    content: text,
    created_at: new Date().toISOString()
  }
  testMessages.value.push(userMsg)
  testStreaming.value = true

  const aiMsg = {
    id: Date.now() + 1,
    sender: 'ai',
    content: '',
    created_at: new Date().toISOString(),
    isStreaming: true
  }
  testMessages.value.push(aiMsg)
  scrollDrawerToBottom()
  
  // 获取推入数组后的响应式代理对象，确保属性修改能触发 Vue 视图更新
  const reactiveAiMsg = testMessages.value[testMessages.value.length - 1]

  typewriterQueue = ''
  startTypewriter(reactiveAiMsg)

  try {
    const response = await fetch(`${api.baseUrl}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({
        session_id: testActiveSessionId.value,
        content: text
      })
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.msg || err.detail || '流式调试对话建立失败。')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue

        if (trimmed.startsWith('data: ')) {
          const dataStr = trimmed.slice(6)
          if (dataStr === '[DONE]') break

          try {
            const parsed = JSON.parse(dataStr)
            if (parsed.content) {
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
    if (!reactiveAiMsg.content) {
      testMessages.value = testMessages.value.filter(m => m.id !== reactiveAiMsg.id)
    }
    console.error('Send test message failed:', error)
  } finally {
    reactiveAiMsg.isStreaming = false
    testStreaming.value = false
    scrollDrawerToBottom()
  }
}

// Clear current session
const handleClearTestSession = async () => {
  if (!testActiveSessionId.value || testStreaming.value) return
  try {
    await api.delete(`/chat/sessions/${testActiveSessionId.value}`)
    const newSess = await api.post('/chat/sessions', {
      title: `调试 - ${props.textbook.title}`,
      textbook_id: props.textbook.id
    })
    testActiveSessionId.value = newSess.id
    testMessages.value = []
    scrollDrawerToBottom()
  } catch (error) {
    console.error('Failed to clear test session:', error)
  }
}

const handleEnterKeyInTest = () => {
  if (testStreaming.value) return
  handleSendTestMessage()
}
</script>

<style scoped>
/* --- Test Drawer Styles --- */
.test-drawer-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.15);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  justify-content: flex-end;
  z-index: 1000;
}

.test-drawer {
  width: 100%;
  max-width: 500px;
  height: 100%;
  background-color: rgba(255, 255, 255, 0.85);
  border-left: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  box-shadow: -10px 0 25px -5px rgba(0, 0, 0, 0.1), -8px 0 10px -6px rgba(0, 0, 0, 0.05);
}

.drawer-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.drawer-title-area h3 {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
}

.drawer-subtitle {
  font-size: 0.775rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.2s ease;
}

.close-btn:hover {
  opacity: 1;
}

.drawer-messages-viewport {
  flex-grow: 1;
  overflow-y: auto;
  padding: 1.5rem;
  background-color: var(--bg-base);
  display: flex;
  flex-direction: column;
}

.drawer-message-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.drawer-empty-state {
  margin: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  color: var(--text-muted);
  gap: 0.75rem;
  max-width: 320px;
}

.drawer-empty-state .empty-icon {
  font-size: 3rem;
  color: var(--color-primary);
  background-color: rgba(37, 99, 235, 0.05);
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.drawer-empty-state h4 {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}

.drawer-empty-state p {
  font-size: 0.775rem;
  line-height: 1.5;
}

.drawer-input-panel {
  padding: 1.25rem 1.5rem;
  border-top: 1px solid var(--border-color);
  background-color: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.drawer-input-form {
  display: flex;
  gap: 0.75rem;
  align-items: flex-end;
}

.drawer-input-form .text-input {
  flex-grow: 1;
  resize: none;
  font-size: 0.85rem;
  padding: 0.5rem 0.75rem;
  line-height: 1.4;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  min-height: 40px;
}

.drawer-input-form .text-input:focus {
  border-color: var(--color-primary);
  outline: none;
}

.drawer-input-form .send-btn {
  padding: 0.5rem 1rem;
  font-size: 0.825rem;
  height: 40px;
  display: flex;
  align-items: center;
  gap: 0.25rem;
  white-space: nowrap;
}

.drawer-input-actions {
  display: flex;
  justify-content: flex-start;
}

.btn-clear-session {
  background: none;
  border: none;
  font-size: 0.75rem;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.25rem;
  transition: color 0.2s ease;
  padding: 0.25rem 0;
}

.btn-clear-session:hover {
  color: var(--color-danger);
}

/* Message wrappers inside drawer */
.drawer-message-list .message-wrapper {
  display: flex;
  gap: 0.75rem;
  max-width: 85%;
}

.drawer-message-list .message-wrapper.user {
  align-self: flex-end;
  flex-direction: row-reverse;
  margin-left: auto;
}

.drawer-message-list .message-wrapper.ai {
  align-self: flex-start;
  margin-right: auto;
}

.drawer-message-list .message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: #ffffff;
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.95rem;
  box-shadow: var(--shadow-sm);
  flex-shrink: 0;
}

.drawer-message-list .message-bubble {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.drawer-message-list .bubble-content {
  padding: 0.65rem 0.85rem;
  border-radius: var(--radius-md);
  font-size: 0.825rem;
  line-height: 1.45;
  word-break: break-word;
  box-shadow: var(--shadow-sm);
  white-space: pre-wrap;
}

.drawer-message-list .user .bubble-content {
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: #ffffff;
  border-top-right-radius: 2px;
}

.drawer-message-list .user .message-time {
  text-align: right;
}

.drawer-message-list .ai .bubble-content {
  background-color: #f1f5f9;
  color: var(--text-primary);
  border-top-left-radius: 2px;
  border: 1px solid #e2e8f0;
}

.drawer-message-list .message-time {
  font-size: 0.65rem;
  color: var(--text-muted);
  padding: 0 0.25rem;
}

/* Blinking typewriter cursor */
.drawer-message-list .streaming-cursor {
  display: inline-block;
  width: 2px;
  height: 1.1em;
  background-color: var(--color-primary);
  margin-left: 2px;
  vertical-align: middle;
  animation: blink 0.8s step-end infinite;
}

/* Animations and Transitions for Drawer */
.slide-left-enter-active, .slide-left-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-left-enter-from, .slide-left-leave-to {
  opacity: 0;
}

.slide-left-enter-from .test-drawer, .slide-left-leave-to .test-drawer {
  transform: translateX(100%);
}

.animate-slide-left {
  animation: slideInLeft 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideInLeft {
  from {
    transform: translateX(100%);
  }
  to {
    transform: translateX(0);
  }
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
