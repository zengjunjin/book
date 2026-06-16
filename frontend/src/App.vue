<template>
  <div class="app" :class="{ 'dark-mode': isDarkMode }">
    <!-- AI 助手页：全屏独立，无侧边栏 -->
    <template v-if="isAIPage">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </template>
    <!-- 登录注册页：全屏独立 -->
    <template v-else-if="isAuthPage">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </template>
    <!-- 普通页：侧边栏 + 主内容 -->
    <template v-else>
      <el-container>
        <AppSidebar />
        <el-main>
          <router-view v-slot="{ Component }">
            <transition name="page" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './components/AppSidebar.vue'

const route = useRoute()
const isAuthPage = computed(() => {
  return route.path === '/login' || route.path === '/register'
})
const isAIPage = computed(() => {
  return route.path === '/ai' || route.path.startsWith('/ai')
})

// 暗色模式切换
const isDarkMode = ref(true)

// 从 localStorage 读取主题设置
const savedTheme = localStorage.getItem('theme')
if (savedTheme) {
  isDarkMode.value = savedTheme === 'dark'
}

// 监听主题变化
watch(isDarkMode, (newVal) => {
  localStorage.setItem('theme', newVal ? 'dark' : 'light')
}, { immediate: true })
</script>

<style>
/* ========== 全局样式 - 深色极客美学 ========== */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  /* 极简配色系统 */
  --bg-primary: #09090e;
  --bg-secondary: #0f0f17;
  --bg-card: rgba(255, 255, 255, 0.04);
  --border-color: rgba(255, 255, 255, 0.07);
  --border-hover: rgba(255, 255, 255, 0.12);
  --text-primary: #e2e8f0;
  --text-secondary: #64748b;
  --text-muted: #475569;
  --accent: #6366f1;
  --accent-light: #818cf8;
  --accent-glow: rgba(99, 102, 241, 0.3);
  --accent-cyan: #22d3ee;
  --success: #34d399;
  --warning: #fbbf24;
  --danger: #f87171;
  --easing-smooth: cubic-bezier(0.16, 1, 0.3, 1);
}

body {
  font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

.app {
  min-height: 100vh;
  background-color: var(--bg-primary);
}

/* 页面切换过渡动画 */
.page-enter-active,
.page-leave-active {
  transition: all 0.4s var(--easing-smooth);
}

.page-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.page-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

.el-main {
  padding: 0;
  background-color: var(--bg-primary);
  min-height: 100vh;
  color: var(--text-primary);
}

/* ========== Element Plus 主题覆盖 ========== */
:root {
  --el-color-primary: #6366f1;
  --el-color-primary-light-3: #818cf8;
  --el-color-primary-light-5: #a5b4fc;
  --el-color-primary-light-7: #c7d2fe;
  --el-color-primary-light-8: #e0e7ff;
  --el-color-primary-light-9: #eef2ff;
  --el-color-primary-dark-2: #4f46e5;
  --el-bg-color: var(--bg-secondary);
  --el-bg-color-overlay: var(--bg-card);
  --el-text-color-primary: var(--text-primary);
  --el-text-color-regular: var(--text-secondary);
  --el-text-color-secondary: var(--text-muted);
  --el-text-color-placeholder: var(--text-muted);
  --el-border-color: var(--border-color);
  --el-border-color-light: rgba(255, 255, 255, 0.05);
  --el-fill-color: var(--bg-card);
  --el-fill-color-light: rgba(255, 255, 255, 0.03);
  --el-fill-color-blank: var(--bg-primary);
  --el-color-success: var(--success);
  --el-color-warning: var(--warning);
  --el-color-danger: var(--danger);
  --el-color-info: var(--text-muted);
  --el-border-radius-base: 10px;
  --el-border-radius-small: 8px;
}

/* 卡片 */
.el-card {
  background-color: var(--bg-card) !important;
  border: 1px solid var(--border-color) !important;
  border-radius: 12px !important;
  color: var(--text-primary);
  transition: border-color 0.25s var(--easing-smooth), transform 0.25s var(--easing-smooth), box-shadow 0.25s var(--easing-smooth);
}

.el-card:hover {
  border-color: var(--accent-light) !important;
  transform: scale(1.01);
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.1);
}

.el-card__header {
  border-bottom-color: var(--border-color) !important;
  color: var(--text-primary) !important;
  font-weight: 600;
  padding: 16px 20px;
}

.el-card__body {
  padding: 20px;
}

/* 输入框 */
.el-input__wrapper {
  background-color: var(--bg-secondary) !important;
  box-shadow: 0 0 0 1px var(--border-color) inset !important;
  border-radius: 10px;
  transition: border-color 0.25s var(--easing-smooth), box-shadow 0.25s var(--easing-smooth);
}

.el-input__wrapper:hover,
.el-input__wrapper.is-focus {
  box-shadow: 0 0 0 1px var(--accent) inset !important;
}

.el-input__inner {
  color: var(--text-primary) !important;
  font-size: 14px;
}

.el-input__inner::placeholder {
  color: var(--text-muted) !important;
}

.el-input__prefix {
  color: var(--text-muted);
}

/* 按钮 */
.el-button--primary {
  background-color: var(--accent) !important;
  border-color: var(--accent) !important;
  color: #fff !important;
  font-weight: 500;
  border-radius: 10px;
  transition: all 0.25s var(--easing-smooth);
}

.el-button--primary:hover {
  background-color: var(--accent-light) !important;
  border-color: var(--accent-light) !important;
  transform: scale(1.02);
  box-shadow: 0 4px 16px var(--accent-glow);
}

.el-button {
  background-color: transparent !important;
  border: 1px solid var(--border-color) !important;
  color: var(--text-primary) !important;
  border-radius: 10px;
  transition: all 0.25s var(--easing-smooth);
}

.el-button:hover {
  border-color: var(--accent-light) !important;
  color: var(--accent-light) !important;
  transform: scale(1.02);
}

/* 表格 */
.el-table {
  background-color: var(--bg-card) !important;
  border-radius: 12px;
  overflow: hidden;
}

.el-table tr {
  background-color: var(--bg-card) !important;
}

.el-table th.el-table__cell {
  background-color: rgba(255, 255, 255, 0.03) !important;
  color: var(--text-primary) !important;
  font-weight: 600;
  border-bottom-color: var(--border-color) !important;
}

.el-table td.el-table__cell {
  border-bottom-color: var(--border-color) !important;
  color: var(--text-primary) !important;
}

.el-table--border .el-table__cell {
  border-right-color: var(--border-color) !important;
}

/* 分页 */
.el-pagination {
  color: var(--text-secondary) !important;
}

.el-pagination .el-pager li {
  background-color: var(--bg-card) !important;
  color: var(--text-secondary) !important;
  border: 1px solid var(--border-color) !important;
  border-radius: 8px;
  margin: 0 4px;
  transition: all 0.25s var(--easing-smooth);
}

.el-pagination .el-pager li:not(.is-active):hover {
  color: var(--accent-light) !important;
  border-color: var(--accent-light) !important;
}

.el-pagination .el-pager li.is-active {
  background-color: var(--accent) !important;
  color: #fff !important;
  border-color: var(--accent) !important;
}

.el-pagination button {
  background-color: var(--bg-card) !important;
  color: var(--text-secondary) !important;
  border: 1px solid var(--border-color) !important;
  border-radius: 8px;
}

.el-pagination button:disabled {
  opacity: 0.5;
}

.el-pagination .el-pagination__total,
.el-pagination .el-pagination__jump,
.el-pagination .el-pagination__sizes .el-input .el-input__inner {
  color: var(--text-secondary) !important;
}

/* 标签页 */
.el-tabs__item {
  color: var(--text-muted) !important;
  font-size: 15px;
  font-weight: 500;
  transition: color 0.25s var(--easing-smooth);
}

.el-tabs__item:hover {
  color: var(--text-primary) !important;
}

.el-tabs__item.is-active {
  color: var(--accent-light) !important;
}

.el-tabs__active-bar {
  background-color: var(--accent) !important;
  height: 2px;
}

.el-tabs__nav-wrap::after {
  background-color: var(--border-color) !important;
}

/* 消息提示 */
.el-message {
  background-color: var(--bg-card) !important;
  border: 1px solid var(--border-color) !important;
  border-radius: 12px;
}

.el-message .el-message__content {
  color: var(--text-primary) !important;
}

.el-message--success {
  border-color: var(--success) !important;
}

.el-message--warning {
  border-color: var(--warning) !important;
}

.el-message--error {
  border-color: var(--danger) !important;
}

/* 加载中 */
.el-loading-mask {
  background-color: rgba(9, 9, 14, 0.9) !important;
}

.el-loading-text {
  color: var(--accent-light) !important;
}

.el-loading-spinner .circular {
  stroke: var(--accent) !important;
}

/* 评分组件 */
.el-rate__icon {
  color: var(--border-color);
  font-size: 18px;
}

.el-rate .el-rate__icon.is-active {
  color: var(--accent-cyan) !important;
}

/* 空状态 */
.el-empty__description p {
  color: var(--text-muted) !important;
}

.el-empty__image svg {
  opacity: 0.3;
}

/* Tag */
.el-tag {
  background-color: var(--bg-card) !important;
  border: 1px solid var(--border-color) !important;
  color: var(--accent-light) !important;
  border-radius: 8px;
  font-size: 12px;
}

/* 对话框 */
.el-dialog {
  background-color: var(--bg-secondary) !important;
  border: 1px solid var(--border-color) !important;
  border-radius: 14px;
}

.el-dialog__header {
  border-bottom: 1px solid var(--border-color);
  padding: 20px 24px;
}

.el-dialog__title {
  color: var(--text-primary) !important;
  font-weight: 600;
}

.el-dialog__body {
  color: var(--text-secondary);
  padding: 24px;
}

/* ========== 滚动条美化 ========== */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: var(--bg-primary);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
  transition: all 0.2s ease;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--accent-light);
}

::-webkit-scrollbar-corner {
  background: var(--bg-primary);
}

/* 页面头部通用样式 */
.page-header {
  margin-bottom: 32px;
}

.page-header h1 {
  color: var(--text-primary);
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 700;
  font-family: 'Space Grotesk', sans-serif;
}

.page-header .subtitle {
  color: var(--text-muted);
  margin: 0;
  font-size: 14px;
}

/* ========== 响应式布局 ========== */
@media (max-width: 1024px) {
  .el-main {
    padding: 0;
  }
}

@media (max-width: 768px) {
  .el-main {
    padding: 0;
  }
}

@media (max-width: 480px) {
  .el-main {
    padding: 0;
  }
}
</style>
