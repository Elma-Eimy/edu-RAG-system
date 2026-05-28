import { useAuthStore } from '../store/auth'
import { useAppStore } from '../store/app'
import router from '../router'

const BASE_URL = 'http://localhost:8000/api/v1'

async function request(path, options = {}) {
  const authStore = useAuthStore()
  const appStore = useAppStore()
  
  // Intercept and throw mock indicator if mock mode is toggled active
  if (appStore.useMock) {
    throw new Error('MOCK_MODE_ACTIVE')
  }
  
  // Construct headers
  const headers = { ...options.headers }
  
  // Attach JWT authorization header if token exists
  if (authStore.token) {
    headers['Authorization'] = `Bearer ${authStore.token}`
  }
  
  // Handle content type
  // If the body is a FormData object (like PDF upload), do not set Content-Type header (browser will set it automatically with boundary)
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
    
    // Auto logout on unauthorized
    if (response.status === 401) {
      authStore.logout()
      router.push('/login')
      throw new Error('会话过期，请重新登录。')
    }

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || `请求失败: ${response.status}`)
    }

    // Check content type for JSON response
    const contentType = response.headers.get('content-type')
    if (contentType && contentType.includes('application/json')) {
      return await response.json()
    }
    
    return await response.text()
  } catch (error) {
    console.error('API Request Error:', error)
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
