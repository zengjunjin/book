<template>
  <div class="book-detail">
    <div v-if="loading" class="loading">
      <el-skeleton :rows="10" animated />
    </div>

    <div v-else-if="book" class="content">
      <div class="book-header">
        <img v-if="book.image_url" :src="book.image_url" :alt="book.title" class="cover" />
        <div v-else class="cover no-cover">暂无封面</div>
        <div class="info">
          <h1>{{ book.title }}</h1>
          <p class="author">{{ book.author || '未知作者' }}</p>
          <p class="meta">{{ book.publisher }} | {{ book.year }}</p>

          <div class="community-rating">
            <h3>社区评分</h3>
            <div class="rating-display">
              <span class="avg">{{ communityRating.avg_rating?.toFixed(1) || 'N/A' }}</span>
              <span class="count">({{ communityRating.rating_count }}人评分)</span>
            </div>
            <div class="distribution">
              <div
                v-for="(count, rating) in communityRating.distribution"
                :key="rating"
                class="bar"
              >
                <span class="label">{{ rating }}</span>
                <div class="bar-fill" :style="{ width: `${(count / communityRating.rating_count) * 100}%` }"></div>
                <span class="count">{{ count }}</span>
              </div>
            </div>
          </div>

          <div class="user-rating">
            <h3>你的评分</h3>
            <div class="rating-buttons">
              <button
                v-for="r in [1,2,3,4,5,6,7,8,9,10]"
                :key="r"
                :class="{ active: userRating === r }"
                @click="submitRating(r)"
              >
                {{ r }}
              </button>
            </div>
          </div>

          <div class="actions">
            <el-button type="primary" @click="toggleLike">
              {{ userInteractions.liked ? '取消喜欢' : '喜欢' }}
            </el-button>
            <el-button @click="toggleWant">
              {{ userInteractions.wanted ? '取消想读' : '想读' }}
            </el-button>
          </div>
        </div>
      </div>

      <div class="description">
        <h3>简介</h3>
        <p>{{ book.description || '暂无简介' }}</p>
      </div>

      <div class="similar-books">
        <h3>相似书籍</h3>
        <div class="book-grid">
          <BookCard
            v-for="b in similarBooks"
            :key="b.id"
            :book="b"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api/client'
import BookCard from '../components/BookCard.vue'

const route = useRoute()
const loading = ref(false)
const book = ref<any>(null)
const communityRating = ref<any>({})
const userRating = ref<number | null>(null)
const userInteractions = ref<any>({})
const similarBooks = ref<any[]>([])

const fetchBookDetail = async () => {
  loading.value = true
  try {
    const bookId = route.params.id
    const response = await api.get(`/books/${bookId}`) as any
    book.value = response
    communityRating.value = response.community_rating || {}
    userRating.value = response.user_rating
    userInteractions.value = response.user_interactions || {}
  } catch (error) {
    console.error('Failed to fetch book detail:', error)
    ElMessage.error('获取书籍详情失败')
  } finally {
    loading.value = false
  }
}

const fetchSimilarBooks = async () => {
  try {
    const bookId = route.params.id
    const response = await api.get(`/books/${bookId}/similar`) as any
    similarBooks.value = response.similar_books?.map((b: any) => ({
      ...b,
      id: b.id,
      image_url: b.image_url
    })) || []
  } catch (error) {
    console.error('Failed to fetch similar books:', error)
  }
}

const submitRating = async (rating: number) => {
  try {
    await api.post('/ratings', {
      book_id: book.value.id,
      rating
    })
    userRating.value = rating
    ElMessage.success('评分成功')
  } catch (error) {
    console.error('Failed to submit rating:', error)
    ElMessage.error('评分失败')
  }
}

const toggleLike = async () => {
  try {
    await api.post('/interactions', {
      book_id: book.value.id,
      interaction_type: 'like'
    })
    userInteractions.value.liked = !userInteractions.value.liked
    ElMessage.success(userInteractions.value.liked ? '已喜欢' : '已取消喜欢')
  } catch (error) {
    console.error('Failed to toggle like:', error)
    ElMessage.error('操作失败')
  }
}

const toggleWant = async () => {
  try {
    await api.post('/interactions', {
      book_id: book.value.id,
      interaction_type: 'want_to_read'
    })
    userInteractions.value.wanted = !userInteractions.value.wanted
    ElMessage.success(userInteractions.value.wanted ? '已加入想读' : '已取消想读')
  } catch (error) {
    console.error('Failed to toggle want:', error)
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  fetchBookDetail()
  fetchSimilarBooks()
})
</script>

<style scoped>
.book-detail {
  padding: 20px;
  max-width: 1000px;
  margin: 0 auto;
}

.loading {
  padding: 20px;
}

.book-header {
  display: flex;
  gap: 24px;
  margin-bottom: 32px;
}

.cover {
  width: 240px;
  height: 360px;
  object-fit: cover;
  border-radius: 8px;
}

.no-cover {
  width: 240px;
  height: 360px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #27272f;
  color: #71717a;
  border-radius: 8px;
}

.info {
  flex: 1;
}

.info h1 {
  color: #e4e4e7;
  font-size: 28px;
  margin-bottom: 8px;
}

.info .author {
  color: #a1a1aa;
  font-size: 18px;
  margin-bottom: 4px;
}

.info .meta {
  color: #71717a;
  font-size: 14px;
  margin-bottom: 24px;
}

.community-rating, .user-rating {
  margin-bottom: 24px;
}

.community-rating h3, .user-rating h3 {
  color: #e4e4e7;
  font-size: 16px;
  margin-bottom: 12px;
}

.rating-display {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 12px;
}

.rating-display .avg {
  font-size: 48px;
  font-weight: bold;
  color: #f97316;
}

.rating-display .count {
  color: #71717a;
}

.distribution {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bar .label {
  width: 20px;
  color: #71717a;
  font-size: 12px;
}

.bar .bar-fill {
  height: 8px;
  background: #f97316;
  border-radius: 4px;
  max-width: 200px;
}

.bar .count {
  color: #71717a;
  font-size: 12px;
  width: 30px;
}

.rating-buttons {
  display: flex;
  gap: 8px;
}

.rating-buttons button {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  border: 1px solid #3f3f46;
  background: #27272f;
  color: #a1a1aa;
  cursor: pointer;
  transition: all 0.2s;
}

.rating-buttons button:hover {
  border-color: #f97316;
  color: #e4e4e7;
}

.rating-buttons button.active {
  background: #f97316;
  border-color: #f97316;
  color: white;
}

.actions {
  display: flex;
  gap: 12px;
}

.description {
  margin-bottom: 32px;
}

.description h3 {
  color: #e4e4e7;
  margin-bottom: 12px;
}

.description p {
  color: #a1a1aa;
  line-height: 1.6;
}

.similar-books h3 {
  color: #e4e4e7;
  margin-bottom: 16px;
}

.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}
</style>
