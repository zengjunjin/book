import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 为所有请求附加当前用户信息
api.interceptors.request.use(
  (config) => {
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    if (user.id) {
      config.params = { ...config.params, user_id: user.id }
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器 - 统一处理 API 错误
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error.message)
    return Promise.reject(error)
  }
)

// ============ 认证相关 ============
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  getMe: (userId) => api.get('/auth/me', { params: { user_id: userId } })
}

// ============ 书籍相关 ============
export const bookAPI = {
  getBooks: (params) => api.get('/books', { params }),
  getBook: (id, params = {}) => api.get(`/books/${id}`, { params }),
  getSimilar: (id) => api.get(`/books/${id}/similar`),
  // 搜索优化相关
  getSuggestions: (q, limit = 10) => api.get('/books/suggestions', { params: { q, limit } }),
  getHotSearch: (limit = 10) => api.get('/books/hot-search', { params: { limit } }),
  getSearchHistory: (userId) => api.get('/books/search-history', { params: { user_id: userId } }),
  addSearchHistory: (userId, term) => api.post('/books/search-history', { user_id: userId, term }),
  clearSearchHistory: (userId) => api.delete('/books/search-history', { data: { user_id: userId } }),
  getCategories: () => api.get('/books/categories'),
  getFilterOptions: () => api.get('/books/filters'),
  getFilteredCount: (params) => api.get('/books/count', { params })
}

// ============ 评分相关 ============
export const ratingAPI = {
  createRating: (data) => api.post('/ratings', data),
  getUserRatings: (userId, page = 1, per_page = 20) =>
    api.get('/ratings/user', { params: { user_id: userId, page, per_page } })
}

// ============ 推荐相关 ============
export const recommendAPI = {
  getCFRecommendations: (userId, n = 20, refresh = true) =>
    api.get('/recommend/cf', { params: { user_id: userId, n, refresh } }),
  getSVDRecommendations: (userId, n = 20, refresh = true) =>
    api.get('/recommend/svd', { params: { user_id: userId, n, refresh } }),
  compareAlgorithms: () => api.get('/recommend/compare')
}

// ============ AI 助手相关 ============
export const aiAPI = {
  // 获取引擎状态（Ollama 是否在线、图书馆数据等）
  getStatus: () => api.get('/ai/status'),

  // 发起对话（非流式）
  chat: (message) => api.post('/ai/chat', { message }),

  // 获取热门书籍（供 AI 助手首页展示）
  getPopular: (limit = 10) => api.get('/ai/popular', { params: { limit } }),

  // 语义搜索（供 AI 或搜索页使用）
  search: (q, limit = 15) => api.get('/ai/search', { params: { q, limit } })
}

export default api
