import { useAuthStore } from '../store/auth'
import { useAppStore } from '../store/app'
import router from '../router'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

async function request(path, options = {}) {
  const authStore = useAuthStore()
  const appStore = useAppStore()
  // 构造请求头
  const headers = { ...options.headers }
  
  // 如果存在 Token，则附加 JWT 授权头
  if (authStore.token) {
    headers['Authorization'] = `Bearer ${authStore.token}`
  }
  
  // 处理内容类型
  // 如果 body 是 FormData 对象（如上传 PDF），不要设置 Content-Type 头（浏览器会自动添加带有 boundary 的首部）
  if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(options.body)
  }

  const url = `${BASE_URL}${path}`
  const fetchOptions = {
    ...options,
    headers
  }

  try {
    const response = await fetch(url, fetchOptions)
    
    // 未授权时自动登出
    if (response.status === 401) {
      authStore.logout()
      router.push('/login')
      throw new Error('会话过期，请重新登录。')
    }

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      let errMsg = errData.msg || errData.detail
      if (!errMsg) {
        // 针对不同 HTTP 状态码进行友好的人性化翻译
        const statusMap = {
          400: '请求参数有误，请检查输入后重试。',
          403: '您没有权限执行此操作。',
          404: '请求的页面或资源未找到。',
          422: '输入的数据格式校验失败，请检查输入。',
          500: '服务器开小差了，请稍后再试。',
          502: '网关响应错误，请稍后重试。',
          503: '系统服务维护中，请稍后再试。',
          504: '网关超时，服务器响应慢，请稍后。'
        }
        errMsg = statusMap[response.status] || `请求失败 (错误码: ${response.status})`
      }
      throw new Error(errMsg)
    }

    // 检查 JSON 响应的内容类型
    const contentType = response.headers.get('content-type')
    if (contentType && contentType.includes('application/json')) {
      return await response.json()
    }
    
    return await response.text()
  } catch (error) {
    console.error('API Request Error:', error)
    // 捕获前端网络连接失败（如后端服务未启动）
    if (error.name === 'TypeError' && (error.message.includes('Failed to fetch') || error.message.includes('fetch'))) {
      throw new Error('网络连接异常：请检查网络设置或确认后端服务已正常启动。')
    }
    throw error
  }
}

export const api = {
  get: (path, options = {}) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options = {}) => request(path, { ...options, method: 'POST', body }),
  put: (path, body, options = {}) => request(path, { ...options, method: 'PUT', body }),
  delete: (path, options = {}) => request(path, { ...options, method: 'DELETE' }),
  baseUrl: BASE_URL
}
export default api
