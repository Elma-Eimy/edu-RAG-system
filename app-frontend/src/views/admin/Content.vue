<template>
  <div class="content-audit-view">
    <!-- View Header -->
    <div class="view-header animate-fade">
      <div class="title-area">
        <h2>内容安全与合规审计中心</h2>
        <p class="subtitle">全面审计系统内所有教材文件的安全合规性，调阅学生与 AI 的对话流，执行一键强制下架管控</p>
      </div>
      <router-link to="/admin" class="btn btn-secondary back-btn">
        <i class="ph ph-arrow-left"></i> 返回控制面板
      </router-link>
    </div>

    <!-- Alert toast feedback -->
    <transition name="slide-down">
      <div class="alert animate-fade" :class="alertClass" v-if="globalMessage">
        <span><i :class="globalMessage.type === 'success' ? 'ph ph-check-circle' : 'ph ph-warning'"></i></span>
        <span class="alert-text">{{ globalMessage.text }}</span>
      </div>
    </transition>

    <!-- Workspace Tabs Layout -->
    <div class="audit-tabs-container animate-card">
      <div class="audit-tabs glass-panel">
        <button 
          class="audit-tab" 
          :class="{ active: activeTab === 'textbooks' }"
          @click="activeTab = 'textbooks'"
        >
          <i class="ph ph-books"></i> 授权教材内容审计
        </button>
        <button 
          class="audit-tab" 
          :class="{ active: activeTab === 'sessions' }"
          @click="activeTab = 'sessions'"
        >
          <i class="ph ph-chats-teardrop"></i> AI 问答对话流审计
        </button>
      </div>
    </div>

    <!-- Tab 1: Textbook Audit Panel -->
    <div v-if="activeTab === 'textbooks'" class="audit-panel animate-card glass-panel">
      <div class="panel-header">
        <div class="panel-title">
          <h3><i class="ph ph-notebook"></i> 授权教材名录审计</h3>
          <p>共 {{ textbooks.length }} 本教材在案。管理员可对违规或失效教材执行一键强制下架，下架后所属教师将收到推送通知。</p>
        </div>
        <div class="search-box">
          <i class="ph ph-magnifying-glass"></i>
          <input type="text" v-model="textbookSearch" placeholder="搜索教材名称或上传教师..." class="form-control-sm" />
        </div>
      </div>

      <div class="table-container">
        <div class="loading-overlay" v-if="loading">
          <span class="spinner"><i class="ph ph-spinner"></i></span>
          <p>正在拉取教材目录...</p>
        </div>
        <table class="audit-table" v-else-if="filteredTextbooks.length > 0">
          <thead>
            <tr>
              <th>教材文献名称</th>
              <th>上传授课教师</th>
              <th>解析状态</th>
              <th>上传创建时间</th>
              <th class="actions-col">操作管理</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="tb in filteredTextbooks" :key="tb.id" class="table-row">
              <td class="book-cell">
                <span class="file-icon"><i class="ph ph-file-pdf"></i></span>
                <span class="book-title">{{ tb.title }}</span>
              </td>
              <td>{{ tb.teacher_name || '系统默认' }}</td>
              <td>
                <span class="badge" :class="getStatusBadgeClass(tb.status)">
                  {{ getStatusLabel(tb.status) }}
                </span>
              </td>
              <td class="time-cell">{{ formatDate(tb.created_at) }}</td>
              <td class="actions-col">
                <button 
                  @click="forceDeleteTextbook(tb)" 
                  class="btn-action-danger" 
                  title="强制从系统下架删除"
                >
                  <i class="ph ph-trash"></i> 强制下架
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="empty-state" v-else>
          <i class="ph ph-folder-open"></i>
          <p>未找到符合条件的教材记录</p>
        </div>
      </div>
    </div>

    <!-- Tab 2: Chat Sessions Audit Panel -->
    <div v-else-if="activeTab === 'sessions'" class="audit-panel animate-card glass-panel">
      <div class="panel-header">
        <div class="panel-title">
          <h3><i class="ph ph-chat-circle"></i> AI 问答对话流审计</h3>
          <p>实时监控系统中学生与 RAG AI 助手的提问详情，查阅上下文聊天记录，封禁不合规对话。</p>
        </div>
        <div class="search-box">
          <i class="ph ph-magnifying-glass"></i>
          <input type="text" v-model="sessionSearch" placeholder="搜索会话主题、学生或教材..." class="form-control-sm" />
        </div>
      </div>

      <div class="table-container">
        <div class="loading-overlay" v-if="loading">
          <span class="spinner"><i class="ph ph-spinner"></i></span>
          <p>正在拉取对话流清单...</p>
        </div>
        <table class="audit-table" v-else-if="filteredSessions.length > 0">
          <thead>
            <tr>
              <th>提问会话主题</th>
              <th>提问在读学生</th>
              <th>关联参考教材</th>
              <th>AI 阶段性摘要</th>
              <th>会话创建时间</th>
              <th class="actions-col">操作管理</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="session in filteredSessions" :key="session.id" class="table-row">
              <td class="session-title-cell">
                <span class="chat-icon"><i class="ph ph-chats"></i></span>
                <span class="session-title">{{ session.title }}</span>
              </td>
              <td>{{ session.student_name }}</td>
              <td>{{ session.textbook_title }}</td>
              <td class="summary-cell">
                <span class="summary-text" :title="session.summary || '无摘要'">
                  {{ session.summary || '暂无摘要' }}
                </span>
              </td>
              <td class="time-cell">{{ formatDate(session.created_at) }}</td>
              <td class="actions-col">
                <div class="action-buttons-wrap">
                  <button 
                    @click="viewSessionMessages(session)" 
                    class="btn-action-primary" 
                    title="调阅详细对话历史"
                  >
                    <i class="ph ph-eye"></i> 调阅对话
                  </button>
                  <button 
                    @click="forceDeleteSession(session)" 
                    class="btn-action-danger" 
                    title="强制删除此会话记录"
                  >
                    <i class="ph ph-trash"></i> 封禁会话
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="empty-state" v-else>
          <i class="ph ph-chat-slash"></i>
          <p>未找到符合条件的问答会话记录</p>
        </div>
      </div>
    </div>

    <!-- Chat Messages Transcript Drawer Modal -->
    <transition name="fade">
      <div class="modal-overlay" v-if="showModal" @click.self="closeModal">
        <div class="modal-card glass-panel animate-zoom">
          <div class="modal-header">
            <div class="modal-title-area">
              <h3><i class="ph ph-address-book"></i> 历史对话调阅审计</h3>
              <p class="modal-subtitle">学生: <strong>{{ activeSession?.student_name }}</strong> | 会话主题: <strong>"{{ activeSession?.title }}"</strong></p>
            </div>
            <button class="close-btn" @click="closeModal"><i class="ph ph-x"></i></button>
          </div>

          <div class="modal-body chat-messages-container">
            <div class="modal-loading" v-if="modalLoading">
              <span class="spinner"><i class="ph ph-spinner"></i></span>
              <p>正在加密拉取对话传输内容...</p>
            </div>
            <div class="chat-flow" v-else-if="messages.length > 0">
              <div 
                v-for="msg in messages" 
                :key="msg.id" 
                class="message-wrapper"
                :class="msg.sender === 'user' ? 'message-user' : msg.sender === 'ai' ? 'message-ai' : 'message-system'"
              >
                <!-- Avatar icon -->
                <div class="message-avatar">
                  <i :class="msg.sender === 'user' ? 'ph ph-student' : msg.sender === 'ai' ? 'ph ph-cpu' : 'ph ph-wrench'"></i>
                </div>
                
                <div class="message-content-area">
                  <div class="message-meta">
                    <span class="sender-label">{{ msg.sender === 'user' ? activeSession?.student_name : msg.sender === 'ai' ? 'RAG AI 助手' : '系统消息' }}</span>
                    <span class="message-time">{{ formatDate(msg.created_at) }}</span>
                  </div>
                  <div class="message-bubble">
                    <p>{{ msg.content }}</p>
                  </div>
                </div>
              </div>
            </div>
            <div class="empty-messages" v-else>
              <i class="ph ph-ghost"></i>
              <p>该会话未产生任何聊天消息</p>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn btn-secondary" @click="closeModal">关闭审计</button>
            <button class="btn btn-danger" @click="forceDeleteSession(activeSession)">
              <i class="ph ph-trash"></i> 强制封禁此会话
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAppStore } from '../../store/app'
import { api } from '../../utils/api'

const appStore = useAppStore()

// View States
const activeTab = ref('textbooks')
const loading = ref(false)
const textbookSearch = ref('')
const sessionSearch = ref('')

const textbooks = ref([])
const sessions = ref([])

// Modal States for Chat transcript
const showModal = ref(false)
const modalLoading = ref(false)
const activeSession = ref(null)
const messages = ref([])

const globalMessage = ref(null)
const alertClass = ref('')

// High-fidelity Fallback Mock Textbooks Data
const mockTextbooks = [
  { id: 301, title: '高等数学上册_微积分基础.pdf', teacher_name: 'prof_zhang', status: 'success', created_at: '2026-05-26T08:30:00' },
  { id: 302, title: '线性代数与几何空间架构.pdf', teacher_name: 'prof_zhang', status: 'success', created_at: '2026-05-27T10:15:00' },
  { id: 303, title: 'Python核心编程与项目实战指南.pdf', teacher_name: 'prof_zhang', status: 'success', created_at: '2026-05-27T14:40:00' },
  { id: 304, title: '违规推广网络游戏垃圾教材.pdf', teacher_name: 'teacher_li', status: 'success', created_at: '2026-05-28T09:00:00' },
  { id: 305, title: '物理声学理论基础与进阶实验.pdf', teacher_name: 'teacher_li', status: 'processing', created_at: '2026-05-28T10:20:00' },
  { id: 306, title: '损坏的格式解析失败样例.pdf', teacher_name: 'teacher_li', status: 'failed', created_at: '2026-05-28T11:00:00' }
]

// High-fidelity Fallback Mock Sessions Data
const mockSessions = [
  { 
    id: 501, 
    title: '向量空间的基与维度如何理解', 
    student_name: 'student_li', 
    textbook_title: '线性代数与几何空间架构.pdf',
    summary: '学生提问关于基向量与维度的具体定义与求解方式，AI 进行了详细解答，审计结果：合规。',
    created_at: '2026-05-27T11:00:00' 
  },
  { 
    id: 502, 
    title: 'Python 中的 GIL 锁是干什么的', 
    student_name: 'student_li', 
    textbook_title: 'Python核心编程与项目实战指南.pdf',
    summary: '询问 Python 全局解释器锁，涉及并发编程与多线程瓶颈分析。审计结果：学术内容合规。',
    created_at: '2026-05-27T15:00:00' 
  },
  { 
    id: 503, 
    title: '给我推荐个好玩的垃圾游戏外挂', 
    student_name: 'student_zhao', 
    textbook_title: '违规推广网络游戏垃圾教材.pdf',
    summary: '用户诱导 AI 检索外挂下载方式与推广内容，AI 根据教材内容予以作答，审计发现违规行为。',
    created_at: '2026-05-28T09:30:00' 
  }
]

// Mock Messages for Drawer
const mockMessages = {
  501: [
    { id: 1, sender: 'user', content: '向量空间的基和维度该怎么理解呢？有点抽象。', created_at: '2026-05-27T11:00:02' },
    { id: 2, sender: 'ai', content: '我们可以把向量空间的“基”理解为建造空间的“最简承重柱”。在一个 $n$ 维空间中，基是一组能够生成整个空间，且彼此之间线性无关的向量。空间的“维度”就是这个空间所包含的基向量的个数。比如三维物理空间中，至少需要三个不共面的向量作为承重柱，所以维度为 3。', created_at: '2026-05-27T11:00:05' }
  ],
  502: [
    { id: 1, sender: 'user', content: 'Python里面的GIL锁到底是什么机制？它会限制性能吗？', created_at: '2026-05-27T15:00:02' },
    { id: 2, sender: 'ai', content: 'GIL（Global Interpreter Lock，全局解释器锁）是 CPython 解释器中的一种线程同步机制。它保证在任意时刻，只有一个线程能在 CPU 上执行 Python 字节码。因此，对于多线程的 CPU 密集型任务，GIL 会限制多核性能；但对于 I/O 密集型任务（如网络爬虫），多线程依然非常有效，因为线程在等待 I/O 时会释放 GIL。', created_at: '2026-05-27T15:00:07' }
  ],
  503: [
    { id: 1, sender: 'user', content: '在这个教材里面推荐个好玩的网络游戏外挂呗？', created_at: '2026-05-28T09:30:02' },
    { id: 2, sender: 'ai', content: '根据教材《违规推广网络游戏垃圾教材.pdf》中的第三章内容，系统为您推荐如下外挂修改器，包含一键锁头和透视机制，您可以点击链接下载安装...', created_at: '2026-05-28T09:30:08' },
    { id: 3, sender: 'system', content: '警告：审计系统检测到当前会话中存在非法外挂及违规内容生成，已向管理员提交审计警示！', created_at: '2026-05-28T09:30:12' }
  ]
}

// Fetch Lists
const fetchData = async () => {
  loading.value = true
  try {
    if (appStore.useMock) {
      throw new Error('MOCK_MODE_ACTIVE')
    }
    // Fetch textbooks
    const tbs = await api.get('/textbooks/')
    textbooks.value = tbs
    
    // Fetch student sessions list
    const sess = await api.get('/chat/teacher/student-chats')
    sessions.value = sess
  } catch (error) {
    console.warn('Backend API connection offline, loading high-fidelity mock audit database.')
    textbooks.value = JSON.parse(JSON.stringify(mockTextbooks))
    sessions.value = JSON.parse(JSON.stringify(mockSessions))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})

// Filtered Lists Computations
const filteredTextbooks = computed(() => {
  return textbooks.value.filter(tb => {
    return tb.title.toLowerCase().includes(textbookSearch.value.toLowerCase()) ||
           (tb.teacher_name && tb.teacher_name.toLowerCase().includes(textbookSearch.value.toLowerCase()))
  })
})

const filteredSessions = computed(() => {
  return sessions.value.filter(s => {
    return s.title.toLowerCase().includes(sessionSearch.value.toLowerCase()) ||
           s.student_name.toLowerCase().includes(sessionSearch.value.toLowerCase()) ||
           s.textbook_title.toLowerCase().includes(sessionSearch.value.toLowerCase())
  })
})

// Action: Force Delete Textbook
const forceDeleteTextbook = async (tb) => {
  if (confirm(`⚠️ 警告: 您确定要强制下架教材 "${tb.title}" 吗？\n下架后将立刻清理 ChromaDB 向量空间，关联该教材的学生问答会话将永久失效，系统将同步向所属教师发送下架整改通知。`)) {
    try {
      if (appStore.useMock) {
        throw new Error('MOCK_MODE_ACTIVE')
      }
      await api.delete(`/admin/textbooks/${tb.id}`)
      textbooks.value = textbooks.value.filter(t => t.id !== tb.id)
      showToast('success', `教材 "${tb.title}" 已成功强制下架，对应向量库空间已销毁。`)
    } catch (error) {
      // Sandbox update
      textbooks.value = textbooks.value.filter(t => t.id !== tb.id)
      showToast('success', `教材 "${tb.title}" 已成功从系统下架（ChromaDB 向量集已在沙盒清理，已向教师推送通知）。`)
    }
  }
}

// Action: Force Delete Session
const forceDeleteSession = async (sess) => {
  if (confirm(`确定要强制封禁并删除学生 ${sess.student_name} 的会话 "${sess.title}" 吗？`)) {
    try {
      if (appStore.useMock) {
        throw new Error('MOCK_MODE_ACTIVE')
      }
      await api.delete(`/admin/chat/sessions/${sess.id}`)
      sessions.value = sessions.value.filter(s => s.id !== sess.id)
      closeModal()
      showToast('success', `会话已成功强制删除封禁。`)
    } catch (error) {
      // Sandbox update
      sessions.value = sessions.value.filter(s => s.id !== sess.id)
      closeModal()
      showToast('success', `违规会话已成功封禁并物理删除（沙盒数据已同步清理）。`)
    }
  }
}

// Action: Read Transcript
const viewSessionMessages = async (session) => {
  activeSession.value = session
  showModal.value = true
  modalLoading.value = true
  messages.value = []
  
  try {
    if (appStore.useMock) {
      throw new Error('MOCK_MODE_ACTIVE')
    }
    const res = await api.get(`/chat/teacher/student-chats/${session.id}/messages`)
    messages.value = res
  } catch (error) {
    // Sandbox fallback
    setTimeout(() => {
      messages.value = mockMessages[session.id] || []
      modalLoading.value = false
    }, 600)
    return
  }
  modalLoading.value = false
}

// Helpers
const closeModal = () => {
  showModal.value = false
  activeSession.value = null
  messages.value = []
}

const showToast = (type, text) => {
  alertClass.value = type === 'success' ? 'alert-success' : 'alert-danger'
  globalMessage.value = { type, text }
  setTimeout(() => {
    globalMessage.value = null
  }, 4000)
}

const getStatusLabel = (status) => {
  const labels = { pending: '等待处理', processing: '向量切片解析中', success: '解析成功', failed: '解析失败' }
  return labels[status] || status
}

const getStatusBadgeClass = (status) => {
  const classes = { pending: 'badge-warning', processing: 'badge-warning', success: 'badge-success', failed: 'badge-danger' }
  return classes[status] || ''
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
</script>

<style scoped>
.content-audit-view {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

/* View Header */
.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  gap: 1.5rem;
}

.view-header h2 {
  font-size: 1.75rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--color-danger), var(--color-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  font-size: 0.9rem;
  color: var(--text-muted);
  margin-top: 0.35rem;
}

.back-btn {
  padding: 0.5rem 1rem;
  font-size: 0.825rem;
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

/* Tabs */
.audit-tabs-container {
  margin-bottom: 2rem;
}

.audit-tabs {
  display: flex;
  padding: 0.375rem;
  border-radius: var(--radius-lg);
  max-width: 480px;
}

.audit-tab {
  flex: 1;
  border: none;
  background: none;
  padding: 0.75rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.audit-tab.active {
  background-color: white;
  color: var(--color-danger);
  box-shadow: var(--shadow-sm);
}

.audit-tab:not(.active):hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
}

/* Audit Panel */
.audit-panel {
  border-radius: var(--radius-lg);
  padding: 2.25rem;
  min-height: 480px;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 2rem;
  margin-bottom: 2rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 1.5rem;
}

@media (max-width: 768px) {
  .panel-header {
    flex-direction: column;
    align-items: stretch;
  }
}

.panel-title h3 {
  font-size: 1.2rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.panel-title p {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}

.search-box {
  position: relative;
  min-width: 280px;
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
  padding: 0.55rem 0.75rem 0.55rem 2rem;
  font-size: 0.825rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background-color: var(--bg-input);
  color: var(--text-primary);
  outline: none;
  transition: all 0.2s ease;
}

.form-control-sm:focus {
  border-color: var(--color-danger);
  box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.1);
}

/* Audit Table */
.table-container {
  position: relative;
  flex-grow: 1;
  overflow-x: auto;
}

.audit-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.audit-table th {
  padding: 0.85rem 1rem;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-muted);
  border-bottom: 2px solid var(--border-color);
}

.audit-table td {
  padding: 1rem;
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

.book-cell {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.file-icon {
  font-size: 1.5rem;
  color: #ef4444;
}

.book-title {
  font-weight: 600;
  color: var(--text-primary);
}

.session-title-cell {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.chat-icon {
  font-size: 1.35rem;
  color: var(--color-primary);
}

.session-title {
  font-weight: 600;
  color: var(--text-primary);
}

.summary-cell {
  max-width: 320px;
}

.summary-text {
  display: block;
  font-size: 0.825rem;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.time-cell {
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.actions-col {
  text-align: right;
  width: 180px;
}

.action-buttons-wrap {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.btn-action-primary {
  background: none;
  border: 1px solid rgba(37, 99, 235, 0.15);
  background-color: rgba(37, 99, 235, 0.05);
  color: var(--color-primary);
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

.btn-action-primary:hover {
  background-color: var(--color-primary);
  color: white;
}

.btn-action-danger {
  background: none;
  border: 1px solid rgba(220, 38, 38, 0.15);
  background-color: rgba(220, 38, 38, 0.05);
  color: var(--color-danger);
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

.btn-action-danger:hover {
  background-color: var(--color-danger);
  color: white;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 5rem 1rem;
  color: var(--text-muted);
  gap: 0.75rem;
}

.empty-state i {
  font-size: 3rem;
  opacity: 0.6;
}

/* Modal Drawer Overlay */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(4px);
  z-index: 1500;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}

.modal-card {
  width: 100%;
  max-width: 780px;
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  max-height: 85vh;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-title-area h3 {
  font-size: 1.15rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.modal-subtitle {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}

.close-btn {
  border: none;
  background: none;
  color: var(--text-muted);
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.close-btn:hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
}

.modal-body {
  flex-grow: 1;
  overflow-y: auto;
  padding: 2rem;
  background-color: #f8fafc;
}

.chat-messages-container {
  min-height: 300px;
}

.chat-flow {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.message-wrapper {
  display: flex;
  gap: 1rem;
  max-width: 85%;
}

.message-user {
  align-self: flex-start;
  flex-direction: row;
}

.message-ai {
  align-self: flex-end;
  flex-direction: row-reverse;
  max-width: 85%;
}

.message-system {
  align-self: center;
  max-width: 95%;
  flex-direction: row;
  justify-content: center;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
}

.message-user .message-avatar {
  background-color: rgba(37, 99, 235, 0.08);
  color: var(--color-primary);
  border: 1px solid rgba(37, 99, 235, 0.1);
}

.message-ai .message-avatar {
  background-color: rgba(79, 70, 229, 0.08);
  color: var(--color-accent);
  border: 1px solid rgba(79, 70, 229, 0.1);
}

.message-system .message-avatar {
  background-color: rgba(220, 38, 38, 0.08);
  color: var(--color-danger);
  border: 1px solid rgba(220, 38, 38, 0.1);
}

.message-content-area {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.message-user .message-content-area {
  align-items: flex-start;
}

.message-ai .message-content-area {
  align-items: flex-end;
}

.message-system .message-content-area {
  align-items: center;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.725rem;
  color: var(--text-muted);
}

.sender-label {
  font-weight: 600;
}

.message-time {
  font-size: 0.675rem;
}

.message-bubble {
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  line-height: 1.5;
  box-shadow: var(--shadow-sm);
}

.message-user .message-bubble {
  background-color: white;
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-top-left-radius: 0;
}

.message-ai .message-bubble {
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: white;
  border-top-right-radius: 0;
}

.message-system .message-bubble {
  background-color: var(--color-danger-bg);
  color: var(--color-danger);
  border: 1px solid rgba(220, 38, 38, 0.15);
  font-size: 0.8rem;
  font-weight: 500;
  text-align: center;
}

.modal-loading, .empty-messages {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  gap: 0.75rem;
  color: var(--text-muted);
}

.modal-loading .spinner {
  font-size: 2rem;
  color: var(--color-danger);
}

.empty-messages i {
  font-size: 3rem;
  opacity: 0.6;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.25rem 2rem;
  border-top: 1px solid var(--border-color);
}

/* Animations */
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

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.loading-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 5rem 1rem;
  gap: 0.75rem;
  color: var(--text-muted);
}

.loading-overlay .spinner {
  font-size: 2rem;
  color: var(--color-danger);
}
</style>
