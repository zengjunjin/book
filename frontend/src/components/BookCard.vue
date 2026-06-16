<template>
  <el-card class="book-card" shadow="hover" @click="goToDetail">
    <div class="book-cover">
      <img v-if="book.image_url" :src="book.image_url" :alt="book.title" loading="lazy" />
      <div v-else class="no-image">
        <el-icon :size="32"><Picture /></el-icon>
      </div>
      <div v-if="book.predicted_rating" class="rating-badge">
        <el-icon><StarFilled /></el-icon>
        {{ Number(book.predicted_rating).toFixed(1) }}
      </div>
      <div v-if="showReason" class="reason-tag" :class="reasonClass">
        {{ recommendReason }}
      </div>
      <div class="cover-overlay">
        <span class="view-detail">查看详情</span>
      </div>
    </div>
    <div class="book-info">
      <h3 class="title" :title="book.title" v-html="highlightText(book.title, searchKeyword)"></h3>
      <p class="author" v-html="highlightText(book.author || '未知作者', searchKeyword)"></p>
      <p class="publisher">{{ book.publisher || '' }}</p>
      <!-- 动态评分星星 -->
      <div class="rating-stars" v-if="book.avg_rating">
        <el-rate
          v-model="displayRating"
          :max="10"
          disabled
          size="small"
          :show-score="false"
          text-color="#f97316"
        />
        <span class="rating-value">{{ (Number(book.avg_rating) || 0).toFixed(1) }}</span>
      </div>
      <div v-if="showQuickRate && userStore.isLoggedIn" class="quick-rate" @click.stop>
        <el-rate
          v-model="quickRating"
          :max="10"
          size="small"
          @change="handleQuickRate"
          text-color="#f97316"
          allow-half
        />
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { StarFilled, Picture } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import { ratingAPI } from '../api'

const props = defineProps({
  book: { type: Object, required: true },
  showQuickRate: { type: Boolean, default: true },
  showReason: { type: Boolean, default: false },
  searchKeyword: { type: String, default: '' }
})

const emit = defineEmits(['rated'])
const router = useRouter()
const userStore = useUserStore()
const quickRating = ref(0)
const submitting = ref(false)

// 高亮搜索关键词
const highlightText = (text, keyword) => {
  if (!keyword || !text) return text
  const regex = new RegExp(`(${keyword})`, 'gi')
  return text.replace(regex, '<mark class="search-highlight">$1</mark>')
}

// 动态评分显示，保留一位小数
const displayRating = computed({
  get: () => Number(props.book.avg_rating) || 0,
  set: (val) => val
})

// 如果 book 里有用户评分，回填
watch(() => props.book, (b) => {
  if (b && b.user_rating) quickRating.value = b.user_rating
}, { immediate: true })

const recommendReason = computed(() => {
  if (!props.book.predicted_rating) return ''
  const score = Number(props.book.predicted_rating)
  if (score >= 8.5) return '🎯 强烈推荐'
  if (score >= 7.5) return '👍 您可能喜欢'
  if (score >= 6.5) return '🤔 值得尝试'
  return '💡 为您推荐'
})

const reasonClass = computed(() => {
  if (!props.book.predicted_rating) return ''
  const score = Number(props.book.predicted_rating)
  if (score >= 8.5) return 'reason-strong'
  if (score >= 7.5) return 'reason-good'
  if (score >= 6.5) return 'reason-maybe'
  return 'reason-default'
})

const goToDetail = () => {
  if (props.book.id) router.push(`/book/${props.book.id}`)
}

const handleQuickRate = async (val) => {
  if (!userStore.isLoggedIn || submitting.value) return
  submitting.value = true
  try {
    await ratingAPI.createRating({
      user_id: userStore.user.id,
      book_id: props.book.id,
      rating: val
    })
    ElMessage.success(`已评分 ${val} 分`)
    emit('rated', { book_id: props.book.id, rating: val })
  } catch (e) {
    ElMessage.error('评分失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.book-card {
  cursor: pointer;
  background-color: #18181f !important;
  border: 1px solid #2a2a35 !important;
  border-radius: 10px;
  color: #e4e4e7;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.book-card:hover {
  border-color: #f97316 !important;
  transform: translateY(-8px) scale(1.02);
  box-shadow: 0 12px 40px rgba(249, 115, 22, 0.2), 0 4px 12px rgba(0, 0, 0, 0.3);
}

.book-card:active {
  transform: translateY(-4px) scale(1.01);
}

.book-cover {
  position: relative;
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #1f1f28 0%, #18181f 100%);
  overflow: hidden;
  flex-shrink: 0;
}

.book-cover img {
  max-height: 200px;
  max-width: 100%;
  object-fit: contain;
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1), filter 0.3s ease;
  filter: brightness(0.95);
}

.book-card:hover .book-cover img {
  transform: scale(1.08);
  filter: brightness(1.05);
}

.no-image {
  color: #3a3a5c;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
}

/* 封面悬浮遮罩 */
.cover-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    180deg,
    rgba(249, 115, 22, 0) 0%,
    rgba(249, 115, 22, 0.1) 50%,
    rgba(249, 115, 22, 0.2) 100%
  );
  opacity: 0;
  transition: opacity 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.book-card:hover .cover-overlay {
  opacity: 1;
}

.view-detail {
  background: rgba(249, 115, 22, 0.9);
  color: white;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  transform: translateY(10px);
  transition: transform 0.3s ease;
}

.book-card:hover .view-detail {
  transform: translateY(0);
}

.rating-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  background: linear-gradient(135deg, #f97316 0%, #fb923c 100%);
  color: #fff;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 4px;
  z-index: 2;
  box-shadow: 0 2px 8px rgba(249, 115, 22, 0.4);
  animation: badgePulse 2s ease-in-out infinite;
}

@keyframes badgePulse {
  0%, 100% { box-shadow: 0 2px 8px rgba(249, 115, 22, 0.4); }
  50% { box-shadow: 0 2px 16px rgba(249, 115, 22, 0.6); }
}

.reason-tag {
  position: absolute;
  bottom: 12px;
  left: 12px;
  background-color: rgba(26, 26, 47, 0.95);
  color: #f97316;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  border: 1px solid rgba(249, 115, 22, 0.3);
  opacity: 0;
  transform: translateY(5px);
  transition: all 0.3s ease;
}

.book-card:hover .reason-tag {
  opacity: 1;
  transform: translateY(0);
}

.reason-strong {
  border-color: rgba(249, 115, 22, 0.6);
  background: linear-gradient(135deg, rgba(249, 115, 22, 0.2) 0%, rgba(26, 26, 47, 0.95) 100%);
}

.reason-good {
  border-color: rgba(34, 197, 94, 0.5);
  color: #22c55e;
}

.reason-maybe {
  border-color: rgba(234, 179, 8, 0.5);
  color: #eab308;
}

.reason-default {
  border-color: rgba(249, 115, 22, 0.3);
  color: #f97316;
}

.book-info {
  padding: 16px;
  display: flex;
  flex-direction: column;
  flex: 1;
  transition: background 0.3s ease;
}

.book-card:hover .book-info {
  background: linear-gradient(180deg, #1f1f28 0%, #18181f 100%);
}

.book-info .title {
  font-size: 14px;
  font-weight: 600;
  color: #e4e4e7;
  margin: 0 0 8px 0;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  min-height: 42px;
  transition: color 0.2s ease;
}

/* 搜索高亮样式 */
:deep(.search-highlight) {
  background-color: rgba(249, 115, 22, 0.3);
  color: #f97316;
  padding: 0 2px;
  border-radius: 2px;
}

.book-card:hover .book-info .title {
  color: #f97316;
}

.book-info .author {
  font-size: 12px;
  color: #71717a;
  margin: 0 0 4px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.2s ease;
}

.book-card:hover .book-info .author {
  color: #a1a1aa;
}

.book-info .publisher {
  font-size: 11px;
  color: #52525b;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 动态评分星星 */
.rating-stars {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #2a2a35;
  animation: ratingFadeIn 0.5s ease-out;
}

@keyframes ratingFadeIn {
  from { opacity: 0; transform: translateX(-10px); }
  to { opacity: 1; transform: translateX(0); }
}

.rating-value {
  color: #f97316;
  font-weight: 600;
  font-size: 13px;
}

:deep(.el-rate__icon) {
  font-size: 14px !important;
}

:deep(.el-rate) {
  --el-rate-icon-color: #2a2a35;
  gap: 2px;
}

.quick-rate {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #2a2a35;
  display: flex;
  justify-content: center;
  transition: all 0.3s ease;
}

:deep(.el-rate) {
  --el-rate-icon-color: #2a2a35;
}

:deep(.el-card__body) {
  padding: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* 响应式 */
@media (max-width: 768px) {
  .book-card:hover {
    transform: translateY(-4px) scale(1.01);
  }

  .rating-badge {
    font-size: 11px;
    padding: 3px 8px;
  }

  .reason-tag {
    font-size: 10px;
    padding: 3px 8px;
  }
}
</style>
