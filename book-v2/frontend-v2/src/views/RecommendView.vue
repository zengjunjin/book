<template>
  <div class="recommend-view">
    <div class="header">
      <div class="title-area">
        <h1><el-icon><MagicStick /></el-icon> 为你推荐</h1>
        <p class="subtitle">协同过滤 & SVD 矩阵分解 — 基于您的评分记录生成个性化推荐</p>
      </div>
      <el-button
        v-if="userStore.isLoggedIn"
        type="primary"
        :loading="loading"
        @click="fetchRecommendations(true)"
        class="refresh-btn"
        :class="{ 'is-refreshing': isRefreshing }"
      >
        <el-icon class="refresh-icon"><Refresh /></el-icon>
        <span>{{ loading ? '刷新中...' : '刷新推荐' }}</span>
      </el-button>
    </div>

    <div v-if="userStore.isLoggedIn" class="status-card">
      <div class="status-item">
        <el-icon :size="24" :color="'#2563eb'"><DataAnalysis /></el-icon>
        <div>
          <div class="status-label">您已评分</div>
          <div class="status-value">{{ userRatingCount }} 本</div>
        </div>
      </div>
      <div class="status-divider"></div>
      <div class="status-item">
        <el-icon :size="24" :color="'var(--text-muted, #94a3b8)'"><InfoFilled /></el-icon>
        <div>
          <div class="status-label">提示</div>
          <div class="status-value hint">{{ recommendationHint }}</div>
        </div>
      </div>
    </div>

    <!-- 加载进度指示器 -->
    <div v-if="loading" class="loading-container">
      <div class="loading-progress">
        <div class="progress-bar"></div>
      </div>
      <p class="loading-text">
        <span class="loading-dot"></span>
        正在分析您的阅读偏好...
      </p>
    </div>

    <div v-else-if="!userStore.isLoggedIn" class="empty-area">
      <el-empty description="请先登录以获取个性化推荐">
        <el-button type="primary" @click="$router.push('/login')">立即登录</el-button>
      </el-empty>
    </div>

    <div v-else>
      <el-tabs v-model="activeTab" class="recommend-tabs" @tab-change="handleTabChange">
        <el-tab-pane label="协同过滤 (User-Based CF)" name="cf">
          <div v-if="cfRecommendations.length === 0" class="empty-small">
            暂无推荐数据 — 尝试为更多书籍评分以获得更好的推荐
          </div>
          <div v-else class="recommend-waterfall" :key="'cf-' + refreshKey">
            <div
              v-for="(book, index) in cfRecommendations"
              :key="book.id"
              class="waterfall-item"
              :style="{ animationDelay: `${index * 50}ms` }"
            >
              <BookCard
                :book="book"
                :show-quick-rate="true"
                :show-reason="true"
              />
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="SVD 矩阵分解" name="svd">
          <div v-if="svdRecommendations.length === 0" class="empty-small">
            暂无推荐数据 — 尝试为更多书籍评分以获得更好的推荐
          </div>
          <div v-else class="recommend-waterfall" :key="'svd-' + refreshKey">
            <div
              v-for="(book, index) in svdRecommendations"
              :key="book.id"
              class="waterfall-item"
              :style="{ animationDelay: `${index * 50}ms` }"
            >
              <BookCard
                :book="book"
                :show-quick-rate="true"
                :show-reason="true"
              />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Refresh, MagicStick, DataAnalysis, InfoFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { recommendAPI, ratingAPI } from '../api'
import { useUserStore } from '../stores/user'
import BookCard from '../components/BookCard.vue'

const userStore = useUserStore()
const activeTab = ref('cf')
const cfRecommendations = ref([])
const svdRecommendations = ref([])
const loading = ref(false)
const userRatingCount = ref(0)
const refreshKey = ref(Date.now())
const isRefreshing = ref(false)

const recommendationHint = computed(() => {
  const n = userRatingCount.value
  if (n < 5) return '评分 ≥ 5 本书，推荐效果会明显提升'
  if (n < 20) return '继续评分更多书籍，可获得更精准的推荐'
  return '您的推荐模型已训练充分 🎉'
})

const fetchUserRatingCount = async () => {
  if (!userStore.isLoggedIn) return
  try {
    const res = await ratingAPI.getUserRatings(1, 1)
    userRatingCount.value = res.total || 0
  } catch (e) {
    // ignore
  }
}

const fetchRecommendations = async (showToast = false) => {
  if (!userStore.isLoggedIn) return
  isRefreshing.value = true
  loading.value = true
  try {
    const [cfRes, svdRes] = await Promise.all([
      recommendAPI.getCFRecommendations(20),
      recommendAPI.getSVDRecommendations(20)
    ])
    cfRecommendations.value = cfRes.recommendations || []
    svdRecommendations.value = svdRes.recommendations || []
    // 更新刷新 key，强制列表重新渲染
    refreshKey.value = Date.now()
    await fetchUserRatingCount()
    if (showToast) {
      ElMessage.success('已为您刷新推荐，看看新的书籍发现吧 👀')
    }
  } catch (err) {
    console.error('加载推荐失败:', err)
    if (showToast) ElMessage.error('刷新失败，请重试')
  } finally {
    loading.value = false
    isRefreshing.value = false
  }
}

const handleTabChange = () => {
  // Tab切换时添加轻微动画
}

onMounted(() => {
  fetchRecommendations()
})
</script>

<style scoped>
.recommend-view {
  padding: 0;
  animation: fadeIn 0.4s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  padding: 0 0 24px 0;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

.title-area h1 {
  color: var(--text-primary, #1e293b);
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-area .subtitle {
  color: var(--text-muted, #94a3b8);
  margin: 0;
  font-size: 14px;
}

/* 刷新按钮动画 */
.refresh-btn {
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
}

.refresh-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(37, 99, 235, 0.15), transparent);
  transition: left 0.5s ease;
}

.refresh-btn:hover::before {
  left: 100%;
}

.refresh-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(249, 115, 22, 0.3);
}

.refresh-icon {
  transition: transform 0.5s ease;
}

.refresh-btn.is-refreshing .refresh-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.status-card {
  display: flex;
  align-items: center;
  padding: 20px 32px;
  background-color: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 10px;
  margin-bottom: 32px;
  gap: 32px;
  animation: slideIn 0.5s ease-out;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateX(-20px); }
  to { opacity: 1; transform: translateX(0); }
}

.status-item {
  display: flex;
  align-items: center;
  gap: 14px;
}

.status-label {
  color: var(--text-muted, #94a3b8);
  font-size: 12px;
  margin-bottom: 4px;
}

.status-value {
  color: var(--text-primary, #1e293b);
  font-size: 18px;
  font-weight: 600;
}

.status-value.hint {
  font-size: 14px;
  color: var(--text-secondary, #475569);
  font-weight: 400;
}

.status-divider {
  width: 1px;
  height: 40px;
  background: var(--border-color, #e2e8f0);
}

/* 加载进度指示器 */
.loading-container {
  padding: 60px 20px;
  text-align: center;
}

.loading-progress {
  width: 200px;
  height: 4px;
  background: var(--border-color, #e2e8f0);
  border-radius: 2px;
  margin: 0 auto 24px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--accent, #2563eb), var(--accent-light, #3b82f6));
  border-radius: 2px;
  animation: progressLoading 1.5s ease-in-out infinite;
}

@keyframes progressLoading {
  0% { width: 0%; margin-left: 0; }
  50% { width: 70%; margin-left: 15%; }
  100% { width: 0%; margin-left: 100%; }
}

.loading-text {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--text-muted, #94a3b8);
  font-size: 14px;
}

.loading-dot {
  width: 8px;
  height: 8px;
  background: linear-gradient(135deg, var(--accent, #2563eb), #0891b2);
  border-radius: 50%;
  animation: dotBounce 1s ease-in-out infinite;
}

@keyframes dotBounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

.recommend-tabs {
  --el-color-primary: var(--accent, #2563eb);
}

/* 瀑布流布局 */
.recommend-waterfall {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 20px;
  padding-top: 24px;
  perspective: 1000px;
}

.waterfall-item {
  animation: waterfallFadeIn 0.5s ease-out forwards;
  opacity: 0;
  transform: translateY(30px) rotateX(10deg);
}

@keyframes waterfallFadeIn {
  to {
    opacity: 1;
    transform: translateY(0) rotateX(0);
  }
}

.loading-area,
.empty-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px 20px;
  text-align: center;
  color: var(--text-muted, #94a3b8);
}

.loading-text {
  margin-top: 24px;
  color: var(--text-muted, #94a3b8);
  font-size: 14px;
}

.empty-small {
  padding: 40px;
  text-align: center;
  color: var(--text-muted, #94a3b8);
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 10px;
  animation: fadeIn 0.4s ease-out;
}

:deep(.el-tabs__item) {
  color: var(--text-muted, #94a3b8) !important;
  font-size: 15px !important;
  transition: all 0.3s ease;
}

:deep(.el-tabs__item.is-active) {
  color: var(--accent, #2563eb) !important;
}

:deep(.el-tabs__active-bar) {
  background-color: var(--accent, #2563eb) !important;
  transition: all 0.3s ease;
}

:deep(.el-tabs__nav-wrap::after) {
  background-color: var(--border-color, #e2e8f0) !important;
}

/* Tab 切换动画 */
:deep(.el-tabs__nav) {
  transition: transform 0.3s ease;
}

/* 响应式布局 */
@media (max-width: 768px) {
  .header {
    flex-direction: column;
    gap: 16px;
  }

  .refresh-btn {
    width: 100%;
  }

  .status-card {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
    padding: 16px;
  }

  .status-divider {
    width: 100%;
    height: 1px;
  }

  .recommend-waterfall {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .waterfall-item {
    animation-delay: 0ms !important;
  }
}

@media (max-width: 480px) {
  .title-area h1 {
    font-size: 22px;
  }

  .recommend-waterfall {
    grid-template-columns: 1fr;
  }
}
</style>
