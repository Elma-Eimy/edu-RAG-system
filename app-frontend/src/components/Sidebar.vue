<template>
  <aside class="sidebar glass-panel">
    <div class="brand">
      <div class="logo-icon"><i class="ph ph-graduation-cap"></i></div>
      <div class="brand-name">SmartEdu</div>
    </div>

    <nav class="nav-menu">
      <!-- Role Label -->
      <div class="role-badge" v-if="authStore.user">
        <span class="badge" :class="roleBadgeClass">
          {{ roleDisplayName }}
        </span>
      </div>

      <!-- Navigation Links -->
      <div class="menu-group">
        <router-link 
          v-for="item in menuItems" 
          :key="item.path" 
          :to="item.path"
          class="menu-item"
          active-class="active"
        >
          <span class="menu-icon"><i :class="item.icon"></i></span>
          <span class="menu-text">{{ item.label }}</span>
        </router-link>
      </div>
    </nav>

    <div class="sidebar-footer">
      <div class="user-info" v-if="authStore.user">
        <div class="avatar">{{ authStore.user.username[0]?.toUpperCase() }}</div>
        <div class="details">
          <div class="username">{{ authStore.user.username }}</div>
          <div class="email">{{ authStore.user.email }}</div>
        </div>
      </div>
      <button class="btn btn-secondary logout-btn" @click="handleLogout">
        <span><i class="ph ph-sign-out"></i></span> Logout
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '../store/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

const roleDisplayName = computed(() => {
  if (!authStore.user) return ''
  const roles = { student: '学生', teacher: '教师', admin: '管理员' }
  return roles[authStore.user.role] || authStore.user.role
})

const roleBadgeClass = computed(() => {
  if (!authStore.user) return ''
  const classes = { student: 'badge-success', teacher: 'badge-warning', admin: 'badge-danger' }
  return classes[authStore.user.role] || ''
})

const menuItems = computed(() => {
  if (!authStore.user) return []
  
  const role = authStore.user.role
  if (role === 'student') {
    return [
      { path: '/student', label: '我的班级', icon: 'ph ph-chalkboard' },
      { path: '/student/chat', label: 'AI 问答书库', icon: 'ph ph-chats-teardrop' }
    ]
  } else if (role === 'teacher') {
    return [
      { path: '/teacher', label: '班级工作台', icon: 'ph ph-chalkboard' },
      { path: '/teacher/textbooks', label: '教材知识库', icon: 'ph ph-books' },
      { path: '/teacher/audit', label: '学生对话审计', icon: 'ph ph-magnifying-glass' }
    ]
  } else if (role === 'admin') {
    return [
      { path: '/admin', label: '用户管理', icon: 'ph ph-users' },
      { path: '/admin/content', label: '内容审计', icon: 'ph ph-shield-check' },
      { path: '/admin/config', label: '大模型系统配置', icon: 'ph ph-wrench' }
    ]
  }
  return []
})

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.sidebar {
  width: 260px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color);
  padding: 1.5rem 1rem;
  position: sticky;
  top: 0;
  z-index: 100;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem;
  margin-bottom: 2rem;
}

.logo-icon {
  font-size: 1.75rem;
}

.brand-name {
  font-size: 1.25rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.nav-menu {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.role-badge {
  padding: 0 0.5rem;
}

.menu-group {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 0.925rem;
  transition: all 0.2s ease;
}

.menu-item:hover {
  background-color: var(--bg-hover);
  color: var(--color-primary);
}

.menu-item.active {
  background-color: rgba(37, 99, 235, 0.08);
  color: var(--color-primary);
  box-shadow: inset 0 1px 2px rgba(37, 99, 235, 0.05);
}

.menu-icon {
  font-size: 1.1rem;
}

.sidebar-footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  border-top: 1px solid var(--border-color);
  padding-top: 1.25rem;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.25rem;
}

.avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 1.1rem;
  box-shadow: var(--shadow-sm);
}

.details {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.username {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.email {
  font-size: 0.75rem;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.logout-btn {
  width: 100%;
  padding: 0.5rem;
  font-size: 0.825rem;
}
</style>
