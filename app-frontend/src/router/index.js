import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../store/auth'

// Route definitions
const routes = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { guestOnly: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: { guestOnly: true }
  },
  {
    path: '/student',
    name: 'StudentDashboard',
    component: () => import('../views/student/Dashboard.vue'),
    meta: { requiresAuth: true, role: 'student' }
  },
  {
    path: '/student/chat/:sessionId?',
    name: 'StudentChat',
    component: () => import('../views/student/Chat.vue'),
    meta: { requiresAuth: true, role: 'student' }
  },
  {
    path: '/teacher',
    name: 'TeacherDashboard',
    component: () => import('../views/teacher/Dashboard.vue'),
    meta: { requiresAuth: true, role: 'teacher' }
  },
  {
    path: '/teacher/class/:classId',
    name: 'ClassDetail',
    component: () => import('../views/teacher/ClassDetail.vue'),
    meta: { requiresAuth: true, role: 'teacher' }
  },
  {
    path: '/teacher/textbooks',
    name: 'TextbookManagement',
    component: () => import('../views/teacher/Textbooks.vue'),
    meta: { requiresAuth: true, role: 'teacher' }
  },
  {
    path: '/teacher/audit',
    name: 'TeacherAudit',
    component: () => import('../views/teacher/Audit.vue'),
    meta: { requiresAuth: true, role: 'teacher' }
  },
  {
    path: '/admin',
    name: 'AdminConsole',
    component: () => import('../views/admin/Console.vue'),
    meta: { requiresAuth: true, role: 'admin' }
  },
  {
    path: '/admin/content',
    name: 'AdminContent',
    component: () => import('../views/admin/Content.vue'),
    meta: { requiresAuth: true, role: 'admin' }
  },
  {
    path: '/admin/config',
    name: 'AdminConfig',
    component: () => import('../views/admin/Config.vue'),
    meta: { requiresAuth: true, role: 'admin' }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../views/NotFound.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

  // Route guard to enforce role-based access control
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  const isAuthenticated = authStore.isAuthenticated
  const userRole = authStore.user?.role

  // Sanity check: if authenticated but user role is corrupt/missing, force logout to prevent redirect loops
  if (isAuthenticated && !userRole) {
    authStore.logout()
    next('/login')
    return
  }

  if (to.meta.requiresAuth && !isAuthenticated) {
    // Not authenticated, redirect to login
    next('/login')
  } else if (to.meta.guestOnly && isAuthenticated) {
    // Authenticated, redirect to respective dashboard
    if (userRole === 'student') next('/student')
    else if (userRole === 'teacher') next('/teacher')
    else if (userRole === 'admin') next('/admin')
    else next('/login')
  } else if (to.meta.role && to.meta.role !== userRole) {
    // Role mismatch, redirect to respective dashboard or login
    if (userRole === 'student') next('/student')
    else if (userRole === 'teacher') next('/teacher')
    else if (userRole === 'admin') next('/admin')
    else next('/login')
  } else {
    next()
  }
})

export default router
