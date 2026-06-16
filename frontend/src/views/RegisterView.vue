<template>
  <div class="auth-page">
    <div class="auth-container">
      <div class="logo-area">
        <h1 class="logo">📚 校园二手书推荐</h1>
        <p class="subtitle">创建您的账号，获取个性化推荐</p>
      </div>

      <el-card class="auth-card" shadow="always">
        <h2 class="title">注册</h2>

        <el-form :model="form" @submit.prevent="handleRegister">
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
              v-model="form.email"
              placeholder="邮箱（可选）"
              size="large"
              clearable
            >
              <template #prefix>
                <el-icon><Message /></el-icon>
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
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item>
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="确认密码"
              size="large"
              show-password
              @keyup.enter="handleRegister"
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
              @click="handleRegister"
              :loading="loading"
              style="width: 100%; font-weight: 600"
            >
              注册
            </el-button>
          </el-form-item>
        </el-form>

        <p class="auth-link">
          已有账号？<router-link to="/login">立即登录</router-link>
        </p>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Message } from '@element-plus/icons-vue'
import { authAPI } from '../api'

const router = useRouter()

const form = ref({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})
const loading = ref(false)

const handleRegister = async () => {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }

  if (form.value.password !== form.value.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  loading.value = true
  try {
    const res = await authAPI.register({
      username: form.value.username,
      email: form.value.email || null,
      password: form.value.password
    })
    if (res.user) {
      ElMessage.success('注册成功，请登录')
      router.push('/login')
    } else {
      ElMessage.error('注册失败')
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '注册失败，请稍后重试')
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
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  padding: 20px;
}

.auth-container {
  width: 100%;
  max-width: 440px;
}

.logo-area {
  text-align: center;
  margin-bottom: 32px;
}

.logo {
  font-size: 28px;
  color: #F97316;
  margin: 0 0 10px 0;
  font-weight: 700;
}

.subtitle {
  color: #909399;
  margin: 0;
  font-size: 14px;
}

.auth-card {
  padding: 12px;
  border-radius: 12px;
}

.title {
  text-align: center;
  color: #F97316;
  margin: 8px 0 24px 0;
  font-size: 24px;
  font-weight: 700;
}

.auth-link {
  text-align: center;
  margin-top: 20px;
  color: #909399;
  font-size: 14px;
}

.auth-link a {
  color: #F97316;
  text-decoration: none;
  font-weight: 500;
}

.auth-link a:hover {
  text-decoration: underline;
}
</style>
