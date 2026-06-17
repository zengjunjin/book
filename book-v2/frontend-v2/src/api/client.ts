import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8001/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 防止多次 401 触发重复跳转的防抖标志
let _isRedirectingToLogin = false

// Request interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      // 清理认证信息
      localStorage.removeItem('token')
      localStorage.removeItem('user')

      // 防抖：多个请求同时返回 401 时只跳转一次
      if (!_isRedirectingToLogin) {
        _isRedirectingToLogin = true
        // 使用 hash 路由正确路径
        window.location.replace('/#/login')
        // 1 秒后重置标志，避免永久阻塞
        setTimeout(() => {
          _isRedirectingToLogin = false
        }, 1000)
      }
    }
    return Promise.reject(error)
  }
)

// ============ 认证相关 ============
export const authAPI = {
  register: (data: { username: string; email?: string; password: string }) =>
    api.post('/auth/register', data),
  login: (data: { username: string; password: string }) => {
    // OAuth2PasswordRequestForm 需要 form-urlencoded 格式
    const formData = new URLSearchParams()
    formData.append('username', data.username)
    formData.append('password', data.password)
    return api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
  },
  getMe: () => api.get('/auth/me')
}

// ============ 书籍相关 ============
export const bookAPI = {
  getBooks: (params: Record<string, any> = {}) => 
    api.get('/books', { params }),
  getBook: (id: number, params: Record<string, any> = {}) => 
    api.get(`/books/${id}`, { params }),
  getSimilar: (id: number) => 
    api.get(`/books/${id}/similar`),
  getSuggestions: (q: string, limit = 10) => 
    api.get('/books/suggestions', { params: { q, limit } }),
  getHotSearch: (limit = 10) => 
    api.get('/books/hot-search', { params: { limit } }),
  getSearchHistory: () =>
    api.get('/books/search-history'),
  addSearchHistory: (term: string) =>
    api.post('/books/search-history', { term }),
  clearSearchHistory: () =>
    api.delete('/books/search-history'),
  getCategories: () => 
    api.get('/books/categories'),
  getFilterOptions: () => 
    api.get('/books/filters'),
  getFilteredCount: (params: Record<string, any>) => 
    api.get('/books/count', { params })
}

// ============ 评分相关 ============
export const ratingAPI = {
  // user_id 由后端从 JWT token 自动提取，前端无需传递
  createRating: (data: { book_id: number; rating: number }) => 
    api.post('/ratings', data),
  getUserRatings: (page = 1, per_page = 20) =>
    api.get('/ratings/user', { params: { page, per_page } })
}

// ============ 推荐相关 ============
// 所有推荐接口的 user_id 由后端从 JWT token 自动提取
export const recommendAPI = {
  getCFRecommendations: (n = 20) =>
    api.get('/recommend/cf', { params: { n } }),
  getSVDRecommendations: (n = 20) =>
    api.get('/recommend/svd', { params: { n } }),
  compareAlgorithms: () => api.get('/recommend/compare')
}

// ============ AI 助手相关 ============
export const aiAPI = {
  getStatus: () => api.get('/ai/status'),
  chat: (message: string) => api.post('/ai/chat', { message }),
  getPopular: (limit = 10) => api.get('/ai/popular', { params: { limit } }),
  search: (q: string, limit = 15) => api.get('/ai/search', { params: { q, limit } })
}

export default api
