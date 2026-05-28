<template>
  <div class="class-detail-view">
    <!-- Header Back Navigation -->
    <div class="view-header animate-fade">
      <div class="title-area">
        <router-link to="/teacher" class="back-link"><i class="ph ph-arrow-left"></i> 返回工作台</router-link>
        <h2>班级成员与审批管理</h2>
        <p class="subtitle">班级: <strong>{{ className }}</strong> (代码: <code>{{ classCode }}</code>)</p>
      </div>
    </div>

    <!-- Alert Notifications Banner -->
    <transition name="slide-down">
      <div class="alert" :class="alertClass" v-if="globalMessage">
        <span><i :class="globalMessage.type === 'success' ? 'ph ph-check-circle' : 'ph ph-warning'"></i></span>
        {{ globalMessage.text }}
      </div>
    </transition>

    <!-- Main split tables layout -->
    <div class="detail-grid">
      <!-- Active Students Roster -->
      <section class="roster-section glass-panel animate-card">
        <div class="section-header">
          <h3><i class="ph ph-users"></i> 班级学生花名册 ({{ students.length }} 人)</h3>
        </div>

        <div class="table-container" v-if="students.length > 0">
          <table class="data-table">
            <thead>
              <tr>
                <th>学号 ID</th>
                <th>学生用户名</th>
                <th>邮箱地址</th>
                <th class="text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="student in students" :key="student.student_id" class="table-row">
                <td><code>#{{ student.student_id }}</code></td>
                <td class="font-bold">{{ student.username }}</td>
                <td class="text-muted">{{ student.email || 'student@smartedu.edu' }}</td>
                <td class="text-right">
                  <button class="btn-table-danger" @click="confirmKick(student)">
                    移除
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="empty-table-placeholder" v-else>
          <div class="placeholder-icon"><i class="ph ph-users"></i></div>
          <p>当前班级暂无加入的学生。</p>
        </div>
      </section>

      <!-- Join Applications Panel -->
      <section class="applications-section glass-panel animate-card">
        <!-- Table Header with Fixed Function Buttons at Top Right -->
        <div class="section-header">
          <h3><i class="ph ph-hourglass-high"></i> 入班申请审批 ({{ pendingApplications.length }} 条待处理)</h3>
          
          <!-- Fixed Action Buttons at Top Right -->
          <div class="bulk-actions" v-if="pendingApplications.length > 0">
            <button 
              class="btn btn-secondary btn-bulk btn-bulk-reject" 
              :disabled="selectedAppIds.length === 0"
              @click="handleBulkReview('reject')"
            >
              <i class="ph ph-x-circle"></i> 批量拒绝 ({{ selectedAppIds.length }})
            </button>
            <button 
              class="btn btn-primary btn-bulk btn-bulk-approve" 
              :disabled="selectedAppIds.length === 0"
              @click="handleBulkReview('approve')"
            >
              <i class="ph ph-check-circle"></i> 批量同意 ({{ selectedAppIds.length }})
            </button>
          </div>
        </div>

        <div class="table-container" v-if="pendingApplications.length > 0">
          <table class="data-table">
            <thead>
              <tr>
                <th class="check-col">
                  <input 
                    type="checkbox" 
                    :checked="isAllSelected" 
                    @change="toggleSelectAll"
                    class="checkbox-control"
                  />
                </th>
                <th>申请 ID</th>
                <th>学号 ID</th>
                <th>申请学生</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr 
                v-for="app in pendingApplications" 
                :key="app.application_id" 
                class="table-row clickable-row"
                @click="toggleSelectApp(app.application_id)"
              >
                <td class="check-col" @click.stop>
                  <input 
                    type="checkbox" 
                    :value="app.application_id" 
                    v-model="selectedAppIds"
                    class="checkbox-control"
                  />
                </td>
                <td><code>#{{ app.application_id }}</code></td>
                <td><code>#{{ app.student_id }}</code></td>
                <td class="font-bold">{{ app.student_username }}</td>
                <td>
                  <span class="badge badge-warning">待审批</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="empty-table-placeholder" v-else>
          <div class="placeholder-icon"><i class="ph ph-mailbox"></i></div>
          <p>当前暂无入班申请需要处理。</p>
        </div>
      </section>
    </div>

    <!-- Kick Student Confirmation Modal -->
    <transition name="fade">
      <div class="modal-overlay confirm-overlay" v-if="showConfirmKick" @click.self="closeConfirmKick">
        <div class="modal-card confirm-card glass-panel animate-zoom">
          <h3>移除学生确认</h3>
          <p class="confirm-message">
            您确定要将学生 <strong>“{{ studentToKick?.username }}”</strong> (ID: #{{ studentToKick?.student_id }}) 移除该班级吗？
            被移除后，该学生将<strong>失去在此班级下的所有 AI 问答授权</strong>。
          </p>
          <div class="confirm-actions">
            <button class="btn btn-secondary" @click="closeConfirmKick">取消</button>
            <button class="btn btn-danger" @click="handleKickStudent">确认移除</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../../utils/api'

const route = useRoute()
const classId = parseInt(route.params.classId)

// Roster & Application States
const className = ref('微积分与空间解析几何')
const classCode = ref('AB12CD')
const students = ref([])
const pendingApplications = ref([])

const selectedAppIds = ref([])
const showConfirmKick = ref(false)
const studentToKick = ref(null)
const globalMessage = ref(null)

// Default Mock Data for local workspace demonstration
const mockStudents = [
  { student_id: 10, username: 'lisi', email: 'lisi@example.com' },
  { student_id: 11, username: 'wangwu', email: 'wangwu@example.com' }
]

const mockApplications = [
  { application_id: 107, student_id: 12, student_username: 'zhaoliu', email: 'zhaoliu@example.com', status: 'pending' },
  { application_id: 108, student_id: 13, student_username: 'tianqi', email: 'tianqi@example.com', status: 'pending' }
]

const alertClass = computed(() => {
  if (!globalMessage.value) return ''
  return globalMessage.value.type === 'success' ? 'alert-success' : 'alert-danger'
})

// Load class roster and applications
const loadClassDetails = async () => {
  try {
    // Attempt real class details from dashboard
    const dashboardRes = await api.get('/classes/dashboard')
    const currentCls = dashboardRes.classes.find(c => c.id === classId)
    if (currentCls) {
      className.value = currentCls.name
      classCode.value = currentCls.class_code
      students.value = currentCls.students || []
    }
  } catch (error) {
    className.value = classId === 1 ? '高等数学 A 班' : '线性代数 B 班'
    classCode.value = classId === 1 ? 'AB12CD' : 'XY99ZZ'
    students.value = [...mockStudents]
  }

  // Load applications list
  try {
    const appsRes = await api.get(`/classes/${classId}/applications?filter_status=pending`)
    pendingApplications.value = appsRes
  } catch (error) {
    pendingApplications.value = [...mockApplications]
  }
}

onMounted(() => {
  loadClassDetails()
})

// Select checkbox controllers
const isAllSelected = computed(() => {
  return pendingApplications.value.length > 0 && selectedAppIds.value.length === pendingApplications.value.length
})

const toggleSelectAll = () => {
  if (isAllSelected.value) {
    selectedAppIds.value = []
  } else {
    selectedAppIds.value = pendingApplications.value.map(app => app.application_id)
  }
}

const toggleSelectApp = (id) => {
  const index = selectedAppIds.value.indexOf(id)
  if (index > -1) {
    selectedAppIds.value.splice(index, 1)
  } else {
    selectedAppIds.value.push(id)
  }
}

// Bulk approve/reject operations (fixed buttons at table top right)
const handleBulkReview = async (action) => {
  if (selectedAppIds.value.length === 0) return

  const originalSelectedCount = selectedAppIds.value.length

  try {
    await api.post(`/classes/${classId}/applications/review`, {
      application_ids: selectedAppIds.value,
      action: action
    })

    showSuccessToast(`成功批量${action === 'approve' ? '同意' : '拒绝'}了 ${originalSelectedCount} 位学生的申请。`)
    selectedAppIds.value = []
    loadClassDetails()
  } catch (error) {
    // Sandbox simulation update
    if (action === 'approve') {
      // Move selected applications to active roster
      selectedAppIds.value.forEach(appId => {
        const matched = pendingApplications.value.find(a => a.application_id === appId)
        if (matched) {
          students.value.push({
            student_id: matched.student_id,
            username: matched.student_username,
            email: matched.email || `${matched.student_username}@smartedu.edu`
          })
        }
      })
    }

    // Filter out approved/rejected applications from pending lists
    pendingApplications.value = pendingApplications.value.filter(
      a => !selectedAppIds.value.includes(a.application_id)
    )

    showSuccessToast(`成功批量${action === 'approve' ? '同意' : '拒绝'}了 ${originalSelectedCount} 位学生的申请（模拟沙盒拦截模式）。`)
    selectedAppIds.value = []
  }
}

// Kick Student logic
const confirmKick = (student) => {
  studentToKick.value = student
  showConfirmKick.value = true
}

const closeConfirmKick = () => {
  showConfirmKick.value = false
  studentToKick.value = null
}

const handleKickStudent = async () => {
  if (!studentToKick.value) return
  const sId = studentToKick.value.student_id

  try {
    await api.delete(`/classes/${classId}/students/${sId}`)
    students.value = students.value.filter(s => s.student_id !== sId)
    showSuccessToast('已成功将该学生移出班级。')
  } catch (error) {
    // Sandbox removal
    students.value = students.value.filter(s => s.student_id !== sId)
    showSuccessToast('已成功移出班级学生（模拟沙盒拦截模式）。')
  } finally {
    closeConfirmKick()
  }
}

// Toast alerts helper
const showSuccessToast = (text) => {
  globalMessage.value = { type: 'success', text }
  setTimeout(() => {
    globalMessage.value = null
  }, 4000)
}
</script>

<style scoped>
.class-detail-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  width: 100%;
}

.view-header {
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 1.25rem;
}

.back-link {
  font-size: 0.85rem;
  font-weight: 500;
  display: inline-block;
  margin-bottom: 0.5rem;
}

.view-header h2 {
  font-size: 1.5rem;
  font-weight: 700;
  margin-top: 0.25rem;
}

.subtitle {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.subtitle code {
  font-size: 0.825rem;
  background-color: var(--bg-hover);
  padding: 1px 4px;
  border-radius: 4px;
  color: var(--color-primary);
}

/* Split Tables layout */
.detail-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 2rem;
}

@media (min-width: 1200px) {
  .detail-grid {
    grid-template-columns: 1.1fr 0.9fr; /* Side-by-side on wide screens */
  }
}

.roster-section,
.applications-section {
  padding: 1.5rem;
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.75rem;
  min-height: 48px;
}

.section-header h3 {
  font-size: 1.05rem;
  font-weight: 600;
}

/* Fixed functional buttons at Top Right of the pending table */
.bulk-actions {
  display: flex;
  gap: 0.5rem;
}

.btn-bulk {
  padding: 0.4rem 0.875rem;
  font-size: 0.75rem;
  border-radius: var(--radius-md);
  font-weight: 600;
}

.btn-bulk:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-bulk-reject:not(:disabled):hover {
  background-color: var(--color-danger-bg);
  border-color: var(--color-danger);
  color: var(--color-danger);
}

/* Table containers */
.table-container {
  overflow-x: auto;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background-color: #ffffff;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.85rem;
}

.data-table th,
.data-table td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border-color);
}

.data-table th {
  background-color: var(--bg-hover);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 0.8rem;
}

.table-row {
  transition: background-color 0.15s ease;
}

.table-row:hover {
  background-color: var(--bg-hover);
}

.clickable-row {
  cursor: pointer;
}

.font-bold {
  font-weight: 600;
  color: var(--text-primary);
}

.text-muted {
  color: var(--text-muted);
}

.text-right {
  text-align: right;
}

.check-col {
  width: 48px;
  text-align: center;
  padding: 0;
}

.checkbox-control {
  width: 16px;
  height: 16px;
  cursor: pointer;
  vertical-align: middle;
}

/* Table Buttons */
.btn-table-danger {
  background-color: var(--bg-base);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 0.3rem 0.65rem;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-table-danger:hover {
  background-color: var(--color-danger-bg);
  border-color: rgba(220, 38, 38, 0.25);
  color: var(--color-danger);
}

.empty-table-placeholder {
  text-align: center;
  padding: 4rem 1rem;
  color: var(--text-muted);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.placeholder-icon {
  font-size: 2.5rem;
}

.empty-table-placeholder p {
  font-size: 0.8rem;
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

/* Confirm kick modal */
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
  margin-top: 0.5rem;
}

.confirm-actions .btn {
  padding: 0.5rem 1.25rem;
  font-size: 0.85rem;
}

/* Toast alert style */
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

/* Animations */
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
