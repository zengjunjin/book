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
              placeholder="用户名（至少3位）"
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
              placeholder="邮箱（选填，不填也可注册）"
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
            <div class="password-rules">
              <span :class="{ 'rule-ok': hasUpper }">大写字母</span>
              <span :class="{ 'rule-ok': hasLower }">小写字母</span>
              <span :class="{ 'rule-ok': hasDigit }">数字</span>
              <span :class="{ 'rule-ok': hasLength }">至少8位</span>
            </div>
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
              :disabled="!isPasswordValid"
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
import { ref, computed } from 'vue'
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

const hasUpper = computed(() => /[A-Z]/.test(form.value.password))
const hasLower = computed(() => /[a-z]/.test(form.value.password))
const hasDigit = computed(() => /\d/.test(form.value.password))
const hasLength = computed(() => form.value.password.length >= 8)
const isPasswordValid = computed(() => hasUpper.value && hasLower.value && hasDigit.value && hasLength.value)

const handleRegister = async () => {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }

  if (!isPasswordValid.value) {
    ElMessage.warning('密码需满足：大写字母、小写字母、数字，且至少8位')
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
      email: form.value.email || undefined,
      password: form.value.password
    })
    if (res.id) {
      ElMessage.success('注册成功，请登录')
      router.push('/login')
    } else {
      ElMessage.error('注册失败')
    }
  } catch (error) {
    const detail = error?.response?.data?.detail
    if (Array.isArray(detail)) {
      ElMessage.error(detail[0]?.msg || '注册失败')
    } else {
      ElMessage.error(detail || '注册失败，请稍后重试')
    }
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
  max-width: 440px;
}

.logo-area {
  text-align: center;
  margin-bottom: 32px;
}

.logo {
  font-size: 28px;
  color: var(--text-primary, #1e293b);
  margin: 0 0 10px 0;
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
  padding: 12px;
}

.title {
  text-align: center;
  color: var(--text-primary, #1e293b);
  margin: 8px 0 24px 0;
  font-size: 24px;
  font-weight: 700;
}

.auth-link {
  text-align: center;
  margin-top: 20px;
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

.password-rules {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
}

.password-rules span {
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--bg-secondary, #f1f5f9);
  border: 1px solid var(--border-color, #e2e8f0);
  transition: all 0.2s;
}

.password-rules span.rule-ok {
  color: var(--success, #059669);
  background: var(--success-soft, #d1fae5);
  border-color: rgba(5, 150, 105, 0.2);
}
</style>
