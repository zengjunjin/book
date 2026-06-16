<template>
  <el-aside width="240px" class="sidebar">
    <div class="logo">
      <div class="logo-icon">📚</div>
      <h2>BookRec</h2>
      <p class="logo-subtitle">个性化图书推荐</p>
    </div>
    <el-menu
      :default-active="$route.path"
      router
      class="sidebar-menu"
      background-color="transparent"
      text-color="#71717a"
      active-text-color="#f97316"
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
  </el-aside>
</template>

<script setup>
import { HomeFilled, StarFilled, TrendCharts, ChatDotRound, UserFilled } from '@element-plus/icons-vue'
</script>

<style scoped>
.sidebar {
  background-color: #18181f;
  min-height: 100vh;
  border-right: 1px solid #2a2a35;
  display: flex;
  flex-direction: column;
}

.logo {
  padding: 32px 24px;
  text-align: center;
  border-bottom: 1px solid #2a2a35;
}

.logo-icon {
  font-size: 32px;
  margin-bottom: 12px;
}

.logo h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #e4e4e7;
  letter-spacing: -0.5px;
}

.logo-subtitle {
  margin: 4px 0 0 0;
  font-size: 12px;
  color: #52525b;
}

.sidebar-menu {
  border: none;
  padding: 16px 12px;
  flex: 1;
}

:deep(.el-menu-item) {
  height: 44px;
  line-height: 44px;
  margin: 4px 0;
  border-radius: 8px;
  padding-left: 16px !important;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

:deep(.el-menu-item:hover) {
  background-color: #22222b !important;
  color: #e4e4e7 !important;
  border-color: #2a2a35;
}

:deep(.el-menu-item.is-active) {
  background-color: rgba(249, 115, 22, 0.1) !important;
  color: #f97316 !important;
  border-color: #f97316;
  border-left: 3px solid #f97316;
}

:deep(.el-menu-item .el-icon) {
  margin-right: 12px;
  font-size: 18px;
}
</style>
