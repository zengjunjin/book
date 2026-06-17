<template>
  <el-aside width="220px" class="sidebar">
    <div class="logo">
      <div class="logo-icon">
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="4" y="6" width="18" height="22" rx="2" stroke="#2563eb" stroke-width="2"/>
          <rect x="10" y="4" width="18" height="22" rx="2" fill="#dbeafe" opacity="0.5"/>
          <path d="M12 10H24M12 14H24M12 18H20" stroke="#2563eb" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </div>
      <h2 class="logo-text">BookRec</h2>
      <p class="logo-subtitle">智能图书推荐</p>
    </div>
    <el-menu
      :default-active="$route.path"
      router
      class="sidebar-menu"
      background-color="transparent"
      text-color="#475569"
      active-text-color="#2563eb"
    >
      <el-menu-item index="/">
        <el-icon><HomeFilled /></el-icon>
        <span>书籍广场</span>
      </el-menu-item>
      <el-menu-item index="/recommend">
        <el-icon><StarFilled /></el-icon>
        <span>为你推荐</span>
      </el-menu-item>
      <el-menu-item index="/compare">
        <el-icon><TrendCharts /></el-icon>
        <span>算法对比</span>
      </el-menu-item>
      <el-menu-item index="/ai">
        <el-icon><ChatDotRound /></el-icon>
        <span>AI 助手</span>
      </el-menu-item>
      <el-menu-item index="/profile">
        <el-icon><UserFilled /></el-icon>
        <span>个人中心</span>
      </el-menu-item>
    </el-menu>
    <div class="sidebar-footer">
      <div class="user-info">
        <div class="avatar">
          <el-avatar :size="32" :src="userAvatar">U</el-avatar>
        </div>
        <span class="username">{{ username }}</span>
      </div>
      <el-button class="logout-btn" :icon="SwitchButton" circle @click="handleLogout" />
    </div>
  </el-aside>
</template>

<script setup>
import { computed } from 'vue'
import { HomeFilled, StarFilled, TrendCharts, ChatDotRound, UserFilled, SwitchButton } from '@element-plus/icons-vue'

const username = computed(() => {
  return localStorage.getItem('username') || '用户'
})

const userAvatar = computed(() => {
  return localStorage.getItem('avatar') || ''
})

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  localStorage.removeItem('userId')
  window.location.href = '/login'
}
</script>

<style scoped>
.sidebar {
  background-color: #ffffff;
  min-height: 100vh;
  border-right: 1px solid var(--border-color, #e2e8f0);
  display: flex;
  flex-direction: column;
}

.logo {
  padding: 28px 20px;
  text-align: center;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

.logo-icon {
  margin-bottom: 12px;
  display: flex;
  justify-content: center;
}

.logo-text {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--accent, #2563eb);
  letter-spacing: -0.5px;
}

.logo-subtitle {
  margin: 4px 0 0 0;
  font-size: 11px;
  color: var(--text-muted, #94a3b8);
}

.sidebar-menu {
  border: none;
  padding: 16px 10px;
  flex: 1;
}

:deep(.el-menu-item) {
  height: 44px;
  line-height: 44px;
  margin: 4px 0;
  border-radius: 10px;
  padding-left: 16px !important;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.25s var(--easing-smooth, cubic-bezier(0.16, 1, 0.3, 1));
  border: 1px solid transparent;
  position: relative;
  color: var(--text-secondary, #475569) !important;
}

:deep(.el-menu-item:hover) {
  background-color: var(--bg-secondary, #f1f5f9) !important;
  color: var(--text-primary, #1e293b) !important;
}

:deep(.el-menu-item.is-active) {
  background-color: var(--accent-soft, #dbeafe) !important;
  color: var(--accent, #2563eb) !important;
  border-color: rgba(37, 99, 235, 0.2);
  font-weight: 600;
}

:deep(.el-menu-item.is-active)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 24px;
  background: var(--accent, #2563eb);
  border-radius: 0 2px 2px 0;
}

:deep(.el-menu-item .el-icon) {
  margin-right: 12px;
  font-size: 18px;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid var(--border-color, #e2e8f0);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2563eb, #0891b2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
}

.username {
  font-size: 13px;
  color: var(--text-secondary, #475569);
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-btn {
  width: 32px;
  height: 32px;
  border: 1px solid var(--border-color, #e2e8f0) !important;
  background: transparent !important;
  color: var(--text-muted, #94a3b8) !important;
  transition: all 0.25s var(--easing-smooth, cubic-bezier(0.16, 1, 0.3, 1));
}

.logout-btn:hover {
  border-color: var(--danger, #dc2626) !important;
  color: var(--danger, #dc2626) !important;
}
</style>
