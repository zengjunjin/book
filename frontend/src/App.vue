<template>
  <div class="app" :class="{ 'dark-mode': isDarkMode }">
    <template v-if="!isAuthPage">
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
    <template v-else>
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
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
/* ========== 全局样式 - 极简科技风 ========== */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  /* 极简配色系统 */
  --bg-primary: #0f0f14;
  --bg-card: #18181f;
  --border-color: #2a2a35;
  --border-hover: #f97316;
  --text-primary: #e4e4e7;
  --text-secondary: #71717a;
  --text-muted: #52525b;
  --accent: #f97316;
  --accent-hover: #fb923c;
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
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
  padding: 48px;
  background-color: var(--bg-primary);
  min-height: 100vh;
  color: var(--text-primary);
}

/* ========== Element Plus 主题覆盖 ========== */
:root {
  --el-color-primary: #f97316;
  --el-color-primary-light-3: #fb923c;
  --el-color-primary-light-5: #fdba74;
  --el-color-primary-light-7: #fed7aa;
  --el-color-primary-light-8: #ffedd5;
  --el-color-primary-light-9: #fff7ed;
  --el-color-primary-dark-2: #c2410c;
  --el-bg-color: var(--bg-card);
  --el-bg-color-overlay: var(--bg-card);
  --el-text-color-primary: var(--text-primary);
  --el-text-color-regular: var(--text-secondary);
  --el-text-color-secondary: var(--text-muted);
  --el-text-color-placeholder: var(--text-muted);
  --el-border-color: var(--border-color);
  --el-border-color-light: #22222b;
  --el-fill-color: var(--bg-card);
  --el-fill-color-light: #1f1f28;
  --el-fill-color-blank: var(--bg-primary);
  --el-color-success: var(--success);
  --el-color-warning: var(--warning);
  --el-color-danger: var(--danger);
  --el-color-info: var(--text-muted);
  --el-border-radius-base: 8px;
  --el-border-radius-small: 6px;
}

/* 卡片 - 扁平化设计 */
.el-card {
  background-color: var(--bg-card) !important;
  border: 1px solid var(--border-color) !important;
  border-radius: 10px !important;
  color: var(--text-primary);
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.el-card:hover {
  border-color: var(--border-hover) !important;
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
  background-color: var(--bg-primary) !important;
  box-shadow: 0 0 0 1px var(--border-color) inset !important;
  border-radius: 8px;
  transition: border-color 0.2s ease;
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
  border-radius: 8px;
  transition: all 0.2s ease;
}

.el-button--primary:hover {
  background-color: var(--accent-hover) !important;
  border-color: var(--accent-hover) !important;
  transform: scale(1.02);
}

.el-button {
  background-color: transparent !important;
  border: 1px solid var(--border-color) !important;
  color: var(--text-primary) !important;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.el-button:hover {
  border-color: var(--accent) !important;
  color: var(--accent) !important;
  transform: scale(1.02);
}

/* 表格 */
.el-table {
  background-color: var(--bg-card) !important;
  border-radius: 10px;
  overflow: hidden;
}

.el-table tr {
  background-color: var(--bg-card) !important;
}

.el-table th.el-table__cell {
  background-color: #1f1f28 !important;
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
  border-radius: 6px;
  margin: 0 4px;
  transition: all 0.2s ease;
}

.el-pagination .el-pager li:not(.is-active):hover {
  color: var(--accent) !important;
  border-color: var(--accent) !important;
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
  border-radius: 6px;
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
  transition: color 0.2s ease;
}

.el-tabs__item:hover {
  color: var(--text-primary) !important;
}

.el-tabs__item.is-active {
  color: var(--accent) !important;
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
  border-radius: 10px;
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
  background-color: rgba(15, 15, 20, 0.9) !important;
}

.el-loading-text {
  color: var(--accent) !important;
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
  color: var(--accent) !important;
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
  color: var(--accent) !important;
  border-radius: 6px;
  font-size: 12px;
}

/* 对话框 */
.el-dialog {
  background-color: var(--bg-card) !important;
  border: 1px solid var(--border-color) !important;
  border-radius: 12px;
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
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: var(--bg-primary);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 4px;
  transition: all 0.2s ease;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--accent);
  box-shadow: 0 0 8px rgba(249, 115, 22, 0.3);
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
}

.page-header .subtitle {
  color: var(--text-muted);
  margin: 0;
  font-size: 14px;
}

/* ========== 响应式布局 ========== */
@media (max-width: 1024px) {
  .el-main {
    padding: 32px;
  }
}

@media (max-width: 768px) {
  .el-main {
    padding: 20px;
  }
}

@media (max-width: 480px) {
  .el-main {
    padding: 12px;
  }
}
</style>
