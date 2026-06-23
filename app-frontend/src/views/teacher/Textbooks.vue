<template>
  <div class="textbooks-view">
    <!-- Top Action Header -->
    <div class="view-header animate-fade">
      <div class="title-area">
        <h2>教材知识库</h2>
        <p class="subtitle">上传 PDF 教材并进行语义切片向量化，将其授权绑定到您的班级</p>
      </div>
      <button 
        class="btn btn-primary toggle-upload-btn" 
        @click="showUploadPanel = !showUploadPanel"
      >
        <i class="ph ph-cloud-arrow-up"></i>
        {{ showUploadPanel ? ' 收起上传面板' : ' 上传新教材' }}
      </button>
    </div>

    <!-- Alert Notifications Banner -->
    <transition name="slide-down">
      <div class="alert" :class="alertClass" v-if="globalMessage">
        <span><i :class="globalMessage.type === 'success' ? 'ph ph-check-circle' : 'ph ph-warning'"></i></span>
        {{ globalMessage.text }}
      </div>
    </transition>

    <!-- Combined Drag-and-Drop & Flat Button Upload Panel -->
    <transition name="slide-down">
      <div class="upload-panel glass-panel animate-fade" v-if="showUploadPanel">
        <h3>上传 PDF 电子教材</h3>
        
        <form @submit.prevent="handleUpload" class="upload-form">
          <div class="form-group">
            <label class="form-label" for="textbookTitle">教材名称</label>
            <input 
              type="text" 
              id="textbookTitle" 
              v-model="uploadTitle" 
              class="form-control" 
              placeholder="请输入教材官方名称（例如：高等数学上册）" 
              required
              :disabled="uploadLoading"
            />
          </div>

          <!-- Combined Dragzone & Native Input -->
          <div 
            class="drag-drop-zone"
            :class="{ active: isDragging, 'has-file': selectedFile }"
            @dragover.prevent="handleDragOver"
            @dragleave.prevent="handleDragLeave"
            @drop.prevent="handleDrop"
            @click="triggerFileSelect"
          >
            <input 
              type="file" 
              ref="fileInput" 
              class="hidden-file-input" 
              accept=".pdf" 
              @change="handleFileSelect"
              :disabled="uploadLoading"
            />
            
            <div class="zone-content" v-if="!selectedFile">
              <span class="upload-icon"><i class="ph ph-upload-simple"></i></span>
              <p class="primary-text">将 PDF 教材拖拽到此处，或点击选择文件</p>
              <p class="secondary-text">仅支持 PDF 格式，文件大小不能超过 50MB</p>
            </div>
            
            <div class="zone-content-selected" v-else>
              <span class="file-icon"><i class="ph ph-file-pdf"></i></span>
              <p class="file-name">{{ selectedFile.name }}</p>
              <p class="file-size">{{ formatBytes(selectedFile.size) }}</p>
              <button type="button" class="btn-clear-file" @click.stop="clearSelectedFile" :disabled="uploadLoading">
                清除文件
              </button>
            </div>
          </div>

          <div class="form-actions">
            <button type="button" class="btn btn-secondary" @click="cancelUpload" :disabled="uploadLoading">
              取消
            </button>
            <button type="submit" class="btn btn-primary" :disabled="uploadLoading || !selectedFile">
              <span class="spinner" v-if="uploadLoading"><i class="ph ph-spinner"></i></span>
              <span v-else>开始上传并解析</span>
            </button>
          </div>
        </form>
      </div>
    </transition>

    <!-- Textbooks List Section -->
    <div class="textbooks-grid" v-if="textbooks.length > 0">
      <div 
        v-for="tb in textbooks" 
        :key="tb.id" 
        class="textbook-card card animate-card"
        :class="{ 'card-failed': tb.status === 'failed' }"
      >
        <div class="card-header">
          <div class="book-avatar"><i class="ph ph-book"></i></div>
          <div class="title-details">
            <h4>{{ tb.title }}</h4>
            <span class="date-label">上传时间: {{ formatDate(tb.created_at) }}</span>
          </div>
          <span class="badge" :class="getStatusBadgeClass(tb.status)">
            {{ getStatusDisplayName(tb.status) }}
          </span>
        </div>

        <div class="card-body">
          <!-- Parsing Progress Capsule Bar -->
          <div class="progress-section" v-if="tb.status === 'processing'">
            <div class="progress-info">
              <span>正在提取切片并计算向量中...</span>
              <span class="progress-val">{{ tb.processing_progress }}%</span>
            </div>
            <!-- Horizontal Capsule Progress Bar -->
            <div class="capsule-progress-bar">
              <div 
                class="progress-fill" 
                :style="{ width: `${tb.processing_progress}%` }"
              ></div>
            </div>
          </div>

          <!-- Pending Status description -->
          <div class="status-desc" v-else-if="tb.status === 'pending'">
            <i class="ph ph-hourglass-high"></i> 已入队，正在等待解析引擎（Celery Task）调度...
          </div>

          <!-- Failed Status description -->
          <div class="status-desc text-danger-desc" v-else-if="tb.status === 'failed'">
            <i class="ph ph-warning"></i> 解析错误。这通常是由于 PDF 文件损坏或文字极度模糊导致 OCR 熔断。
          </div>

          <!-- Success Details -->
          <div class="success-details" v-else>
            <div class="detail-row">
              <span class="label">数据库集合:</span>
              <span class="value"><code>{{ tb.chroma_collection_id || 'textbook_vec_' + tb.id }}</code></span>
            </div>
            <div class="detail-row">
              <span class="label">已绑定班级:</span>
              <span class="value">
                <span class="bound-badge" v-for="cId in tb.boundClasses" :key="cId">
                  #{{ cId }}
                </span>
                <span class="text-muted" v-if="!tb.boundClasses || tb.boundClasses.length === 0">
                  暂无绑定班级
                </span>
              </span>
            </div>
          </div>
        </div>

        <div class="card-actions">
          <!-- If success: allow binding and soft deleting -->
          <template v-if="tb.status === 'success'">
            <button class="btn btn-primary action-btn" @click="openTestDrawer(tb)">
              <i class="ph ph-chat-circle"></i> 测试教材
            </button>
            <button class="btn btn-secondary action-btn" @click="openBindModal(tb)">
              <i class="ph ph-link-simple"></i> 授权绑定班级
            </button>
            <button class="btn-icon-danger" @click="confirmDelete(tb)" title="软下架删除教材">
              下架
            </button>
          </template>

          <!-- If failed: allow reprocess -->
          <template v-else-if="tb.status === 'failed'">
            <button class="btn btn-primary action-btn reprocess-btn" @click="handleReprocess(tb)">
              <i class="ph ph-spinner"></i> 重新提交解析
            </button>
            <button class="btn-icon-danger" @click="confirmDelete(tb)">
              删除
            </button>
          </template>

          <!-- Otherwise disabled actions -->
          <template v-else>
            <div class="working-placeholder">
              <span>后台向量切片计算中...</span>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div class="empty-state glass-panel animate-fade" v-else>
      <div class="empty-illustration"><i class="ph ph-books"></i></div>
      <h3>教材库当前空空如也</h3>
      <p>上传您的第一本 PDF 电子教材，系统将启动 Celery 离线引擎切片向量化并录入 ChromaDB。</p>
      <button class="btn btn-primary" @click="showUploadPanel = true">立即上传教材</button>
    </div>

    <!-- Bind Classes Modal Overlay -->
    <transition name="fade">
      <div class="modal-overlay" v-if="showBindModal" @click.self="closeBindModal">
        <div class="modal-card glass-panel animate-zoom">
          <div class="modal-header">
            <h3>授权教材绑定</h3>
            <button class="close-btn" @click="closeBindModal"><i class="ph ph-x"></i></button>
          </div>

          <p class="modal-desc">
            请选择要将 <strong>“{{ selectedBook?.title }}”</strong> 授权绑定的班级。绑定后，对应班级内的学生方可使用此教材开展 AI 问答。
          </p>

          <form @submit.prevent="handleBindClasses" class="modal-form">
            <div class="classes-check-list" v-if="teacherClasses.length > 0">
              <label 
                v-for="cls in teacherClasses" 
                :key="cls.id" 
                class="class-check-item"
                :class="{ checked: tempClassIds.includes(cls.id) }"
              >
                <input 
                  type="checkbox" 
                  :value="cls.id" 
                  v-model="tempClassIds"
                  class="checkbox-control"
                />
                <div class="item-info">
                  <span class="item-name">{{ cls.name }}</span>
                  <span class="item-code">代码: {{ cls.class_code }}</span>
                </div>
              </label>
            </div>
            
            <div class="empty-classes-alert" v-else>
              <p><i class="ph ph-warning"></i> 您目前名下没有班级。请先在班级工作台创建班级再进行授权绑定。</p>
            </div>

            <div class="modal-actions">
              <button type="button" class="btn btn-secondary" @click="closeBindModal">
                取消
              </button>
              <button 
                type="submit" 
                class="btn btn-primary" 
                :disabled="teacherClasses.length === 0"
              >
                保存授权关系
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
          <h3>下架并软删除教材</h3>
          <p class="confirm-message">
            您确定要下架并软删除教材 <strong>“{{ bookToDelete?.title }}”</strong> 吗？
            系统将同步<strong>清理 ChromaDB 中的全部向量数据</strong>，关联此教材的学生会话将全部中断熔断。
          </p>
          <div class="confirm-actions">
            <button class="btn btn-secondary" @click="closeConfirmDelete">取消</button>
            <button class="btn btn-danger" @click="handleDeleteBook">确认下架</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Chat Test Sandbox Drawer (Decoupled Component) -->
    <ChatSandboxDrawer 
      :show="showTestDrawer" 
      :textbook="selectedBookForTest" 
      @close="closeTestDrawer" 
    />
  </div>
</template>

<script setup>
import { ref, onMounted, computed, onUnmounted, nextTick } from 'vue'
import { api } from '../../utils/api'
import { renderMarkdown } from '../../utils/markdown'
import ChatSandboxDrawer from '../../components/ChatSandboxDrawer.vue'

// Textbooks State
const textbooks = ref([])
const showUploadPanel = ref(false)
const showBindModal = ref(false)
const showConfirmDelete = ref(false)

// Test Drawer State
const showTestDrawer = ref(false)
const selectedBookForTest = ref(null)

// Upload Form state
const uploadTitle = ref('')
const selectedFile = ref(null)
const fileInput = ref(null)
const isDragging = ref(false)
const uploadLoading = ref(false)

// Selection State
const selectedBook = ref(null)
const tempClassIds = ref([])
const bookToDelete = ref(null)

const globalMessage = ref(null)

const teacherClasses = ref([])

// Computed classes
const alertClass = computed(() => {
  if (!globalMessage.value) return ''
  return globalMessage.value.type === 'success' ? 'alert-success' : 'alert-danger'
})

// Polling interval timer
let pollIntervalTimer

// Fetch textbooks list
const fetchTextbooks = async () => {
  try {
    const res = await api.get('/textbooks/')
    // Parse classes bindings if needed
    textbooks.value = res.map(t => ({
      ...t,
      boundClasses: t.boundClasses || []
    }))
    startPollingIfNecessary()
  } catch (error) {
    showErrorToast(error.message || '获取教材列表失败。')
    textbooks.value = []
  }
}

// Fetch teacher classes for binding modal
const fetchTeacherClasses = async () => {
  try {
    const res = await api.get('/classes/dashboard')
    teacherClasses.value = (res.classes || []).map(c => ({
      id: c.id,
      name: c.name,
      class_code: c.class_code
    }))
  } catch (error) {
    console.error('Failed to fetch teacher classes:', error)
    teacherClasses.value = []
  }
}

onMounted(() => {
  fetchTextbooks()
  fetchTeacherClasses()
})

onUnmounted(() => {
  clearInterval(pollIntervalTimer)
})

// Dynamic polling trigger to showcase progress bar updates
const startPollingIfNecessary = () => {
  clearInterval(pollIntervalTimer)
  pollIntervalTimer = setInterval(() => {
    let hasProcessing = false

    textbooks.value.forEach(async (tb) => {
      if (tb.status === 'processing' || tb.status === 'pending') {
        hasProcessing = true
        
        try {
          // Attempt real API status poll
          const res = await api.get(`/textbooks/${tb.id}/status`)
          tb.status = res.status
          tb.processing_progress = res.processing_progress
          tb.chroma_collection_id = res.chroma_collection_id
        } catch (err) {
          console.error('Failed to poll textbook status:', err)
        }
      }
    })

    if (!hasProcessing) {
      clearInterval(pollIntervalTimer)
    }
  }, 3000)
}

// Visual badging
const getStatusBadgeClass = (status) => {
  const mapping = {
    success: 'badge-success',
    processing: 'badge-primary-badge', // custom blue badge
    pending: 'badge-warning',
    failed: 'badge-danger'
  }
  return mapping[status] || ''
}

const getStatusDisplayName = (status) => {
  const mapping = {
    success: '就绪 (Success)',
    processing: '解析中 (Processing)',
    pending: '等待中 (Pending)',
    failed: '解析失败 (Failed)'
  }
  return mapping[status] || status
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

// Drag & Drop Event triggers
const handleDragOver = () => {
  isDragging.value = true
}

const handleDragLeave = () => {
  isDragging.value = false
}

const handleDrop = (e) => {
  isDragging.value = false
  const files = e.dataTransfer.files
  if (files.length > 0) {
    validateAndSetFile(files[0])
  }
}

const triggerFileSelect = () => {
  fileInput.value.click()
}

const handleFileSelect = (e) => {
  const files = e.target.files
  if (files.length > 0) {
    validateAndSetFile(files[0])
  }
}

const validateAndSetFile = (file) => {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showErrorToast('仅支持 PDF 电子教材格式。')
    return
  }
  if (file.size > 50 * 1024 * 1024) {
    showErrorToast('文件大小超过 50MB 限制。')
    return
  }
  selectedFile.value = file
  // Autofill title if empty
  if (!uploadTitle.value) {
    uploadTitle.value = file.name.substring(0, file.name.lastIndexOf('.'))
  }
}

const clearSelectedFile = () => {
  selectedFile.value = null
}

const cancelUpload = () => {
  clearSelectedFile()
  uploadTitle.value = ''
  showUploadPanel.value = false
}

// PDF Upload Submission
const handleUpload = async () => {
  if (!selectedFile.value || uploadLoading.value) return

  uploadLoading.value = true
  
  const formData = new FormData()
  formData.append('title', uploadTitle.value.trim())
  formData.append('file', selectedFile.value)

  try {
    // Attempt actual file POST
    const response = await api.post('/textbooks/upload', formData)
    
    textbooks.value.unshift({
      ...response,
      boundClasses: []
    })
    cancelUpload()
    showSuccessToast('教材上传成功，已排队入库启动异步向量分块！')
    startPollingIfNecessary()
  } catch (error) {
    showErrorToast(error.message || '上传电子教材失败，请重试。')
  } finally {
    uploadLoading.value = false
  }
}

// Retry reprocessing failed book
const handleReprocess = async (tb) => {
  try {
    const res = await api.post(`/textbooks/${tb.id}/reprocess`)
    tb.status = res.status
    showSuccessToast(res.message || '重试任务提交通道成功！')
    startPollingIfNecessary()
  } catch (err) {
    showErrorToast(err.message || '重新提交解析失败。')
  }
}

// Modal Bind classes triggers
const openBindModal = (tb) => {
  selectedBook.value = tb
  tempClassIds.value = [...(tb.boundClasses || [])]
  showBindModal.value = true
}

const closeBindModal = () => {
  showBindModal.value = false
  selectedBook.value = null
}

const handleBindClasses = async () => {
  if (!selectedBook.value) return

  const bookId = selectedBook.value.id
  
  try {
    await api.post(`/textbooks/${bookId}/bind-classes`, { class_ids: tempClassIds.value })
    selectedBook.value.boundClasses = [...tempClassIds.value]
    showSuccessToast('授权绑定成功！')
  } catch (error) {
    showErrorToast(error.message || '授权绑定失败。')
  } finally {
    closeBindModal()
  }
}

// Delete textbook modal control
const confirmDelete = (tb) => {
  bookToDelete.value = tb
  showConfirmDelete.value = true
}

const closeConfirmDelete = () => {
  showConfirmDelete.value = false
  bookToDelete.value = null
}

const handleDeleteBook = async () => {
  if (!bookToDelete.value) return
  const id = bookToDelete.value.id

  try {
    await api.delete(`/textbooks/${id}`)
    textbooks.value = textbooks.value.filter(t => t.id !== id)
    showSuccessToast('教材已成功软下架。')
  } catch (error) {
    showErrorToast(error.message || '下架教材失败，请稍后重试。')
  } finally {
    closeConfirmDelete()
  }
}

// Help utility formatting bytes
const formatBytes = (bytes, decimals = 2) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}

// Toast alerts helper
const showSuccessToast = (text) => {
  globalMessage.value = { type: 'success', text }
  setTimeout(() => {
    globalMessage.value = null
  }, 4000)
}

const showErrorToast = (text) => {
  globalMessage.value = { type: 'error', text }
  setTimeout(() => {
    globalMessage.value = null
  }, 4000)
}

// --- Test Drawer Methods ---

// Open test drawer
const openTestDrawer = (tb) => {
  selectedBookForTest.value = tb
  showTestDrawer.value = true
}

// Close test drawer
const closeTestDrawer = () => {
  showTestDrawer.value = false
  selectedBookForTest.value = null
}
</script>

<style scoped>
.textbooks-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  width: 100%;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 1.25rem;
}

.view-header h2 {
  font-size: 1.5rem;
  font-weight: 700;
}

.subtitle {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.toggle-upload-btn {
  padding: 0.65rem 1.25rem;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
}

/* Upload Panel and DragZone */
.upload-panel {
  background-color: #ffffff;
  padding: 2rem;
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.upload-panel h3 {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
}

.upload-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.drag-drop-zone {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: 2.5rem 1.5rem;
  text-align: center;
  cursor: pointer;
  background-color: var(--bg-hover);
  transition: all 0.25s ease;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.drag-drop-zone:hover,
.drag-drop-zone.active {
  border-color: var(--color-primary);
  background-color: rgba(37, 99, 235, 0.02);
}

.drag-drop-zone.has-file {
  border-style: solid;
  border-color: var(--color-success);
  background-color: rgba(5, 150, 105, 0.01);
}

.hidden-file-input {
  display: none;
}

.zone-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.upload-icon {
  font-size: 2.5rem;
  margin-bottom: 0.25rem;
}

.primary-text {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.secondary-text {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.zone-content-selected {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  width: 100%;
}

.file-icon {
  font-size: 3rem;
  margin-bottom: 0.25rem;
}

.file-name {
  font-size: 0.925rem;
  font-weight: 600;
  color: var(--color-success);
  max-width: 90%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-size {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.btn-clear-file {
  background-color: #ffffff;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 0.35rem 0.75rem;
  border-radius: var(--radius-md);
  font-size: 0.75rem;
  margin-top: 0.5rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-clear-file:hover {
  background-color: var(--color-danger-bg);
  color: var(--color-danger);
  border-color: rgba(220, 38, 38, 0.2);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.form-actions .btn {
  padding: 0.5rem 1.25rem;
}

/* Textbooks Grid cards */
.textbooks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1.5rem;
}

.textbook-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: relative;
  overflow: hidden;
}

.textbook-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--color-accent), var(--color-primary));
}

.textbook-card.card-failed::before {
  background: var(--color-danger);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.book-avatar {
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
  flex-grow: 1;
  min-width: 0;
}

.title-details h4 {
  font-size: 1.025rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.date-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-top: 0.1rem;
}

.card-body {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.status-desc {
  font-size: 0.8rem;
  color: var(--text-muted);
  line-height: 1.5;
  background-color: var(--bg-hover);
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
}

.text-danger-desc {
  background-color: var(--color-danger-bg);
  color: var(--color-danger);
  border: 1px solid rgba(220, 38, 38, 0.1);
}

/* Horizontal Capsule Progress Bar Styling */
.progress-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.progress-val {
  color: var(--color-primary);
  font-family: ui-monospace, monospace;
}

.capsule-progress-bar {
  height: 8px; /* Capsule thickness */
  background-color: var(--bg-hover);
  border-radius: 99px;
  overflow: hidden;
  box-shadow: var(--shadow-inset);
  position: relative;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary), var(--color-accent));
  border-radius: 99px;
  transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.success-details {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  font-size: 0.775rem;
  background-color: var(--bg-hover);
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 24px;
}

.detail-row .label {
  color: var(--text-muted);
}

.detail-row .value {
  color: var(--text-secondary);
  font-weight: 500;
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  justify-content: flex-end;
  max-width: 70%;
}

.detail-row code {
  font-size: 0.75rem;
  padding: 1px 4px;
  background-color: #ffffff;
  border: 1px solid var(--border-color);
}

.bound-badge {
  background-color: var(--color-success-bg);
  color: var(--color-success);
  border: 1px solid rgba(5, 150, 105, 0.15);
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0px 4px;
  border-radius: 4px;
}

.card-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-top: auto;
}

.action-btn {
  flex-grow: 1;
  padding: 0.475rem;
  font-size: 0.8rem;
}

.btn-icon-danger {
  background-color: var(--bg-hover);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 0.475rem 0.75rem;
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-icon-danger:hover {
  background-color: var(--color-danger-bg);
  border-color: rgba(220, 38, 38, 0.3);
  color: var(--color-danger);
}

.working-placeholder {
  flex-grow: 1;
  font-size: 0.775rem;
  color: var(--text-muted);
  text-align: center;
  background-color: var(--bg-hover);
  padding: 0.475rem;
  border-radius: var(--radius-md);
  border: 1px dashed var(--border-color);
}

/* Modals checklist selector */
.modal-desc {
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-top: -0.5rem;
}

.classes-check-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 240px;
  overflow-y: auto;
  padding: 0.25rem;
}

.class-check-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s ease;
  background-color: #ffffff;
}

.class-check-item:hover {
  background-color: var(--bg-hover);
  border-color: var(--text-muted);
}

.class-check-item.checked {
  background-color: rgba(5, 150, 105, 0.02);
  border-color: var(--color-success);
}

.checkbox-control {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.item-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.item-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}

.item-code {
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-top: 0.05rem;
}

.empty-classes-alert {
  padding: 1.5rem 1rem;
  text-align: center;
  font-size: 0.825rem;
  color: var(--text-secondary);
  background-color: var(--color-danger-bg);
  border-radius: var(--radius-md);
  border: 1px solid rgba(220, 38, 38, 0.1);
}

/* Blue badge custom color */
.badge-primary-badge {
  background-color: rgba(37, 99, 235, 0.08);
  color: var(--color-primary);
  border: 1px solid rgba(37, 99, 235, 0.2);
}

/* Custom Empty State style */
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

/* Overlays and Modals */
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
  max-width: 400px;
  text-align: center;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.confirm-message {
  font-size: 0.875rem;
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

/* Alerts */
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

.alert-error {
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
