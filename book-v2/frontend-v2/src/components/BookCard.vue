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
      <div class="rating-stars" v-if="book.avg_rating">
        <el-rate
          v-model="displayRating"
          :max="10"
          disabled
          size="small"
          :show-score="false"
          text-color="#0891b2"
          :colors="['#2563eb', '#3b82f6', '#0891b2']"
        />
        <span class="rating-value">{{ (Number(book.avg_rating) || 0).toFixed(1) }}</span>
      </div>
      <div v-if="showQuickRate && userStore.isLoggedIn" class="quick-rate" @click.stop>
        <el-rate
          v-model="quickRating"
          :max="10"
          size="small"
          @change="handleQuickRate"
          text-color="#0891b2"
          :colors="['#2563eb', '#3b82f6', '#0891b2']"
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
// HTML 转义（防止 XSS）
const escapeHtml = (str) => {
  if (!str) return str
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// 高亮搜索关键词（先转义再插入高亮标签）
const highlightText = (text, keyword) => {
  if (!keyword || !text) return escapeHtml(text)
  const safeText = escapeHtml(text)
  const safeKeyword = escapeHtml(keyword)
  try {
    const escapedKeyword = safeKeyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const regex = new RegExp(`(${escapedKeyword})`, 'gi')
    return safeText.replace(regex, '<mark class="search-highlight">$1</mark>')
  } catch {
    return safeText
  }
}

const displayRating = computed({
  get: () => Number(props.book.avg_rating) || 0,
  set: (val) => val
})

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
  console.log('Rating request:', { book_id: props.book.id, rating: val, bookIdType: typeof props.book.id, ratingType: typeof val })
  try {
    await ratingAPI.createRating({
      book_id: props.book.id,
      rating: val
    })
    ElMessage.success(`已评分 ${val} 分`)
    emit('rated', { book_id: props.book.id, rating: val })
  } catch (e) {
    console.error('Rating error:', e)
    ElMessage.error('评分失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.book-card {
  cursor: pointer;
  background-color: var(--bg-card, #ffffff) !important;
  border: 1px solid var(--border-color, #e2e8f0) !important;
  border-radius: 12px;
  color: var(--text-primary, #1e293b);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.book-card:hover {
  border-color: var(--accent, #2563eb) !important;
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.15), 0 2px 8px rgba(0, 0, 0, 0.08);
}

.book-card:active {
  transform: translateY(-2px);
}

.book-cover {
  position: relative;
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #f1f5f9 0%, #e0e7ff 100%);
  overflow: hidden;
  flex-shrink: 0;
}

.book-cover img {
  max-height: 200px;
  max-width: 100%;
  object-fit: contain;
  transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.book-card:hover .book-cover img {
  transform: scale(1.08);
}

.no-image {
  color: #cbd5e1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
}

.cover-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    180deg,
    rgba(37, 99, 235, 0) 0%,
    rgba(37, 99, 235, 0.08) 50%,
    rgba(37, 99, 235, 0.18) 100%
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
  background: linear-gradient(135deg, #2563eb, #0891b2);
  color: white;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  transform: translateY(10px);
  transition: transform 0.3s ease;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3);
}

.book-card:hover .view-detail {
  transform: translateY(0);
}

.rating-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  background: linear-gradient(135deg, #2563eb 0%, #0891b2 100%);
  color: #fff;
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 4px;
  z-index: 2;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
}

.reason-tag {
  position: absolute;
  bottom: 12px;
  left: 12px;
  background-color: rgba(255, 255, 255, 0.95);
  color: var(--accent, #2563eb);
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 500;
  border: 1px solid rgba(37, 99, 235, 0.25);
  opacity: 0;
  transform: translateY(5px);
  transition: all 0.3s ease;
}

.book-card:hover .reason-tag {
  opacity: 1;
  transform: translateY(0);
}

.reason-strong {
  border-color: rgba(37, 99, 235, 0.5);
  background: linear-gradient(135deg, #dbeafe 0%, #ffffff 100%);
  color: var(--accent-cyan, #0891b2);
}

.reason-good {
  border-color: rgba(34, 197, 94, 0.4);
  background: linear-gradient(135deg, #d1fae5 0%, #ffffff 100%);
  color: #059669;
}

.reason-maybe {
  border-color: rgba(234, 179, 8, 0.4);
  background: linear-gradient(135deg, #fef3c7 0%, #ffffff 100%);
  color: #d97706;
}

.reason-default {
  border-color: rgba(37, 99, 235, 0.25);
  background: linear-gradient(135deg, #dbeafe 0%, #ffffff 100%);
  color: var(--accent, #2563eb);
}

.book-info {
  padding: 16px;
  display: flex;
  flex-direction: column;
  flex: 1;
  transition: background 0.3s ease;
}

.book-card:hover .book-info {
  background: rgba(37, 99, 235, 0.02);
}

.book-info .title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #1e293b);
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

:deep(.search-highlight) {
  background-color: rgba(37, 99, 235, 0.15);
  color: var(--accent, #2563eb);
  padding: 0 2px;
  border-radius: 2px;
}

.book-card:hover .book-info .title {
  color: var(--accent, #2563eb);
}

.book-info .author {
  font-size: 12px;
  color: var(--text-secondary, #475569);
  margin: 0 0 4px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.2s ease;
}

.book-card:hover .book-info .author {
  color: var(--text-primary, #1e293b);
}

.book-info .publisher {
  font-size: 11px;
  color: var(--text-muted, #94a3b8);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rating-stars {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--border-color, #e2e8f0);
}

.rating-value {
  color: var(--accent-cyan, #0891b2);
  font-weight: 600;
  font-size: 13px;
}

:deep(.el-rate__icon) {
  font-size: 14px !important;
}

:deep(.el-rate) {
  --el-rate-icon-color: #cbd5e1;
  --el-rate-void-color: #cbd5e1;
  --el-rate-disabled-void-color: #cbd5e1;
  --el-rate-fill-color: #2563eb;
  gap: 2px;
}

:deep(.el-rate__icon.hover) {
  transform: scale(1.1);
}

.quick-rate {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border-color, #e2e8f0);
  display: flex;
  justify-content: center;
  transition: all 0.3s ease;
}

:deep(.el-card__body) {
  padding: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}

@media (max-width: 768px) {
  .book-card:hover {
    transform: translateY(-2px);
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
