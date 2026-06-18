import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const token = ref(localStorage.getItem('token'))

  // 只检查 token 是否存在，更简单可靠
  // 如果 token 无效，API 会返回 401，拦截器会清理 token 并跳转到登录页
  const isLoggedIn = computed(() => !!token.value)

  const setUser = (userData: any) => {
    user.value = userData
    localStorage.setItem('user', JSON.stringify(userData))
  }

  const setToken = (newToken: string) => {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  const logout = () => {
    user.value = null
    token.value = null
    localStorage.removeItem('user')
    localStorage.removeItem('token')
  }

  const initUser = () => {
    const storedUser = localStorage.getItem('user')
    const storedToken = localStorage.getItem('token')
    if (storedUser && storedToken) {
      user.value = JSON.parse(storedUser)
      token.value = storedToken
    } else {
      // 任何一项缺失，都视为未登录，清理残留数据
      localStorage.removeItem('user')
      localStorage.removeItem('token')
    }
  }

  return { user, token, isLoggedIn, setUser, setToken, logout, initUser }
})
