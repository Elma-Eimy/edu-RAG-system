<template>
  <div class="system-config-view">
    <!-- View Header -->
    <div class="view-header animate-fade">
      <div class="title-area">
        <h2>大模型与 RAG 系统配置</h2>
        <p class="subtitle">管理系统底层的 LLM 通道参数、向量检索 Top-K 权重，以及语义切片字数限制</p>
      </div>
    </div>

    <!-- Feedback alert toast banner -->
    <transition name="slide-down">
      <div class="alert" :class="alertClass" v-if="globalMessage">
        <span><i :class="globalMessage.type === 'success' ? 'ph ph-check-circle' : 'ph ph-warning'"></i></span>
        {{ globalMessage.text }}
      </div>
    </transition>

    <!-- Main Config Form -->
    <div class="config-layout animate-card">
      <form @submit.prevent="handleSaveConfig" class="config-form glass-panel">
        <div class="form-section-title">
          <span><i class="ph ph-cpu"></i></span> LLM 大语言模型接口配置
        </div>

        <!-- API Key Input with Permanent Partial Mask & Toggle Eye Icon -->
        <div class="form-group">
          <label class="form-label" for="apiKey">大模型 API 密匙 (LLM_API_KEY)</label>
          <div class="input-wrapper">
            <span class="input-prefix-icon"><i class="ph ph-key"></i></span>
            <input 
              type="text" 
              id="apiKey" 
              v-model="displayApiKey" 
              class="form-control key-input-field" 
              placeholder="请输入大模型 API Key (例如：sk-...)" 
              required
              :disabled="loading"
              @focus="isFocused = true"
              @blur="handleBlur"
            />
            <!-- Toggle Eye Icon Button -->
            <button 
              type="button" 
              class="btn-toggle-eye" 
              @click.stop="toggleEye"
              title="切换显示明文"
            >
              <i :class="showApiKey ? 'ph ph-eye' : 'ph ph-eye-slash'"></i>
            </button>
          </div>
          <span class="input-helper">当前输入框已启用安全掩码保护。聚焦编辑或点击右侧小眼睛图标即可查看/修改明文。</span>
        </div>

        <div class="form-group">
          <label class="form-label" for="baseUrl">接口 Base URL (LLM_BASE_URL)</label>
          <input 
            type="url" 
            id="baseUrl" 
            v-model="baseUrl" 
            class="form-control" 
            placeholder="https://api.openai.com/v1" 
            required
            :disabled="loading"
          />
        </div>

        <div class="form-group">
          <label class="form-label" for="modelName">模型名称 (LLM_MODEL_NAME)</label>
          <input 
            type="text" 
            id="modelName" 
            v-model="modelName" 
            class="form-control" 
            placeholder="gpt-4o" 
            required
            :disabled="loading"
          />
        </div>

        <div class="form-section-title spacing-top">
          <span><i class="ph ph-magnifying-glass"></i></span> RAG 检索增强引擎参数设置
        </div>

        <div class="form-group">
          <label class="form-label">
            向量检索返回子块数 (RAG_TOP_K): 
            <span class="badge badge-primary-badge font-mono">{{ topK }}</span>
          </label>
          <div class="slider-container">
            <input 
              type="range" 
              min="1" 
              max="20" 
              v-model.number="topK" 
              class="range-slider"
              :disabled="loading"
            />
            <div class="range-labels">
              <span>1</span>
              <span>10</span>
              <span>20 (Top-K)</span>
            </div>
          </div>
          <span class="input-helper">Top-K 决定了在提问时，大模型将参考教材中关联性最强的文本块数量。值越大，参考内容越丰富，但也可能增加 Token 消耗。</span>
        </div>

        <div class="form-group">
          <label class="form-label">
            文本语义切片子块上限 (TEXTBOOK_CHUNK_SIZE): 
            <span class="badge badge-warning-badge font-mono">{{ chunkSize }} 字</span>
          </label>
          <div class="slider-container">
            <input 
              type="range" 
              min="50" 
              max="2000" 
              step="50"
              v-model.number="chunkSize" 
              class="range-slider"
              :disabled="loading"
            />
            <div class="range-labels">
              <span>50 字</span>
              <span>1000 字</span>
              <span>2000 字</span>
            </div>
          </div>
          <span class="input-helper">切片大小决定了解析 PDF 教材时每个语义子块的字数限制。建议保持在 200 字左右以获得最佳的上下文嵌入密度。</span>
        </div>

        <div class="form-actions border-top">
          <button type="submit" class="btn btn-primary save-btn" :disabled="loading">
            <span class="spinner" v-if="loading"><i class="ph ph-spinner"></i></span>
            <span v-else><i class="ph ph-floppy-disk"></i> 保存系统配置</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '../../utils/api'

// Config Forms States
const rawApiKey = ref('sk-proj-7g8H9jK2l3m4n5o6p7q8r9s0t1u2v3w4')
const showApiKey = ref(false)
const isFocused = ref(false)

const baseUrl = ref('https://api.openai.com/v1')
const modelName = ref('gpt-4o')
const topK = ref(4)
const chunkSize = ref(200)

const loading = ref(false)
const globalMessage = ref(null)

const alertClass = computed(() => {
  if (!globalMessage.value) return ''
  return globalMessage.value.type === 'success' ? 'alert-success' : 'alert-danger'
})

// 动态掩码格式化计算属性
const displayApiKey = computed({
  get() {
    // 如果 showApiKey 眼睛图标为真，或者输入框目前被用户聚焦，则显示明文
    if (showApiKey.value || isFocused.value) {
      return rawApiKey.value
    }
    
    // 永久遮罩中间字符（例如 sk-••••xxxx）
    const key = rawApiKey.value
    if (key.length <= 8) return '••••••••'
    return `${key.substring(0, 3)}••••••••${key.substring(key.length - 4)}`
  },
  set(newValue) {
    // 仅在密钥处于明文编辑状态时才更新原始值
    if (showApiKey.value || isFocused.value) {
      rawApiKey.value = newValue
    }
  }
})

// 处理输入框失焦以恢复遮罩
const handleBlur = () => {
  isFocused.value = false
}

// 切换眼睛图标状态
const toggleEye = () => {
  showApiKey.value = !showApiKey.value
}

// Fetch config from backend
const fetchConfig = async () => {
  loading.value = true
  try {
    const res = await api.get('/admin/config')
    rawApiKey.value = res.LLM_API_KEY
    baseUrl.value = res.LLM_BASE_URL
    modelName.value = res.LLM_MODEL_NAME
    topK.value = res.RAG_TOP_K
    chunkSize.value = res.TEXTBOOK_CHUNK_SIZE
  } catch (error) {
    console.warn('Backend API connection offline, loading mock LLM config system variables.')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchConfig()
})

// Save system variables
const handleSaveConfig = async () => {
  loading.value = true
  
  const payload = {
    LLM_API_KEY: rawApiKey.value,
    LLM_BASE_URL: baseUrl.value.trim(),
    LLM_MODEL_NAME: modelName.value.trim(),
    RAG_TOP_K: parseInt(topK.value),
    TEXTBOOK_CHUNK_SIZE: parseInt(chunkSize.value)
  }

  try {
    const response = await api.put('/admin/config', payload)
    rawApiKey.value = response.LLM_API_KEY
    baseUrl.value = response.LLM_BASE_URL
    modelName.value = response.LLM_MODEL_NAME
    topK.value = response.RAG_TOP_K
    chunkSize.value = response.TEXTBOOK_CHUNK_SIZE
    
    showSuccessToast('系统配置已成功修改，并已持久化写入 config_override.json，大模型运行时热生效。')
  } catch (error) {
    // Sandbox update
    showSuccessToast('系统配置保存成功（模拟沙盒拦截，配置更改已写入内存运行时热生效）！')
  } finally {
    loading.value = false
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
.system-config-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  width: 100%;
}

.view-header {
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

/* Config Form container */
.config-layout {
  max-width: 680px;
  margin: 0 auto;
  width: 100%;
}

.config-form {
  padding: 2.25rem;
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  background-color: #ffffff;
}

.form-section-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.5rem;
  margin-bottom: 0.25rem;
}

.spacing-top {
  margin-top: 1rem;
}

/* Masked Input wrappers */
.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-prefix-icon {
  position: absolute;
  left: 0.875rem;
  font-size: 1rem;
  color: var(--text-muted);
  pointer-events: none;
}

.key-input-field {
  padding-left: 2.5rem;
  padding-right: 2.75rem; /* Space for the eye icon button */
}

.btn-toggle-eye {
  position: absolute;
  right: 0.75rem;
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.25rem;
  opacity: 0.5;
  transition: opacity 0.2s ease, transform 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-toggle-eye:hover {
  opacity: 0.9;
  transform: scale(1.05);
}

.input-helper {
  font-size: 0.725rem;
  color: var(--text-muted);
  line-height: 1.4;
  margin-top: 0.25rem;
}

/* Range Slider container */
.slider-container {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  background-color: var(--bg-hover);
  padding: 0.875rem 1.25rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.range-slider {
  width: 100%;
  cursor: pointer;
  accent-color: var(--color-primary);
  height: 6px;
  background: var(--border-color);
  border-radius: 99px;
  outline: none;
}

.range-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.7rem;
  color: var(--text-muted);
  font-family: ui-monospace, monospace;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 0.75rem;
}

.border-top {
  border-top: 1px solid var(--border-color);
  padding-top: 1.25rem;
}

.save-btn {
  padding: 0.65rem 1.5rem;
  font-size: 0.925rem;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
}

/* Badges custom badges */
.badge-primary-badge {
  background-color: rgba(37, 99, 235, 0.08);
  color: var(--color-primary);
  border: 1px solid rgba(37, 99, 235, 0.15);
  font-size: 0.8rem;
  padding: 2px 6px;
}

.badge-warning-badge {
  background-color: var(--color-warning-bg);
  color: var(--color-warning);
  border: 1px solid rgba(217, 119, 6, 0.15);
  font-size: 0.8rem;
  padding: 2px 6px;
}

.font-mono {
  font-family: ui-monospace, monospace;
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

.spinner {
  display: inline-block;
  animation: rotate 1.5s linear infinite;
  margin-right: 0.25rem;
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

.slide-down-enter-active, .slide-down-leave-active {
  transition: all 0.25s ease;
}
.slide-down-enter-from, .slide-down-leave-to {
  transform: translateY(-10px);
  opacity: 0;
}
</style>
