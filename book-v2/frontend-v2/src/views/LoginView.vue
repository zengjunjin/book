<template>
  <div class="auth-page">
    <div class="auth-container">
      <div class="logo-area">
        <h1 class="logo">📚 校园二手书推荐</h1>
        <p class="subtitle">基于协同过滤与 SVD 矩阵分解的智能推荐系统</p>
      </div>

      <el-card class="auth-card" shadow="always">
        <h2 class="title">登录</h2>

        <el-form :model="form" @submit.prevent="handleLogin">
          <el-form-item>
            <el-input
              v-model="form.username"
              placeholder="用户名"
              size="large"
              clearable
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item>
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              size="large"
              show-password
              @keyup.enter="handleLogin"
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              @click="handleLogin"
              :loading="loading"
              style="width: 100%; font-weight: 600"
            >
              登录
            </el-button>
          </el-form-item>
        </el-form>

        <p class="auth-link">
          还没有账号？<router-link to="/register">立即注册</router-link>
        </p>

        <div class="demo-hint">
          <el-icon><InfoFilled /></el-icon>
          <span>提示：数据集中的测试用户无真实密码无法登录。请先<router-link to="/register">注册新账号</router-link>，密码需包含大写字母、小写字母、数字且至少8位。</span>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, InfoFilled } from '@element-plus/icons-vue'
import { authAPI } from '../api'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()

const form = ref({
  username: '',
  password: ''
})
const loading = ref(false)

const handleLogin = async () => {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }

  loading.value = true
  try {
    const res = await authAPI.login(form.value)
    // OAuth2 响应: { access_token, token_type }
    if (res.access_token) {
      userStore.setToken(res.access_token)
      // 获取用户信息
      const me = await authAPI.getMe()
      if (me) {
        userStore.setUser(me)
        ElMessage.success('登录成功！')
        router.push('/')
      } else {
        ElMessage.error('获取用户信息失败')
      }
    } else {
      ElMessage.error('登录失败，请检查用户名和密码')
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || error?.response?.data?.detail || '登录失败，请检查网络连接')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: var(--bg-secondary, #f1f5f9);
  padding: 20px;
}

.auth-container {
  width: 100%;
  max-width: 400px;
}

.logo-area {
  text-align: center;
  margin-bottom: 32px;
}

.logo {
  font-size: 28px;
  color: var(--text-primary, #1e293b);
  margin: 0 0 8px 0;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.subtitle {
  color: var(--text-secondary, #475569);
  margin: 0;
  font-size: 14px;
}

.auth-card {
  padding: 32px;
}

:deep(.el-card__body) {
  padding: 0;
}

.title {
  text-align: center;
  color: var(--text-primary, #1e293b);
  margin: 0 0 32px 0;
  font-size: 22px;
  font-weight: 700;
}

:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-form-item:last-of-type) {
  margin-bottom: 24px;
}

:deep(.el-button--primary) {
  width: 100%;
  height: 44px;
  font-size: 15px;
}

.auth-link {
  text-align: center;
  margin: 24px 0 0 0;
  color: var(--text-secondary, #475569);
  font-size: 14px;
}

.auth-link a {
  color: var(--accent, #2563eb);
  text-decoration: none;
  font-weight: 500;
}

.auth-link a:hover {
  text-decoration: underline;
}

.demo-hint {
  margin-top: 24px;
  padding: 14px 16px;
  background-color: var(--bg-secondary, #f1f5f9);
  border-radius: 8px;
  border: 1px solid var(--border-color, #e2e8f0);
  color: var(--text-secondary, #475569);
  font-size: 13px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.demo-hint .el-icon {
  color: var(--accent, #2563eb);
  flex-shrink: 0;
  margin-top: 2px;
}

.demo-hint b, .demo-hint a {
  color: var(--accent, #2563eb);
}
</style>
