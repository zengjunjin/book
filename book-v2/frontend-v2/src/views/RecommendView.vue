<template>
  <div class="recommend-view">
    <div class="header">
      <h1>为你推荐</h1>
      <div class="controls">
        <el-button @click="refresh" :loading="loading">刷新推荐</el-button>
        <el-select v-model="source" @change="fetchRecommendations">
          <el-option label="混合推荐" value="hybrid" />
          <el-option label="协同过滤" value="cf" />
          <el-option label="SVD推荐" value="svd" />
        </el-select>
      </div>
    </div>

    <div v-if="loading" class="loading">
      <el-skeleton :rows="8" animated />
    </div>

    <div v-else-if="recommendations.length === 0" class="empty">
      <p>暂无推荐，请先评分一些书籍或设置你的兴趣标签</p>
    </div>

    <div v-else class="book-grid">
      <BookCard
        v-for="book in recommendations"
        :key="book.book_id"
        :book="book"
        @interaction-change="handleInteractionChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/client'
import BookCard from '../components/BookCard.vue'

interface Book {
  book_id: number
  id?: number
  title: string
  author?: string
  image_url?: string
  avg_rating?: number
  rating_count: number
}

interface RecommendationResponse {
  recommendations: Book[]
  total: number
  source: string
}

const loading = ref(false)
const source = ref('hybrid')
const recommendations = ref<Book[]>([])
const refreshKey = ref(0)

const fetchRecommendations = async () => {
  loading.value = true
  try {
    const userId = 1 // TODO: get from auth
    const endpoint = source.value === 'hybrid'
      ? `/recommend/hybrid/${userId}`
      : `/recommend/${source.value}/${userId}`

    const response = await api.get(endpoint) as RecommendationResponse
    recommendations.value = response.recommendations.map(r => ({
      ...r,
      id: r.book_id,
      image_url: r.image_url,
      rating_count: 0
    }))
  } catch (error) {
    console.error('Failed to fetch recommendations:', error)
    ElMessage.error('获取推荐失败')
  } finally {
    loading.value = false
  }
}

const refresh = () => {
  refreshKey.value++
  fetchRecommendations()
}

const handleInteractionChange = ({ type, value }: { type: string; value: boolean }) => {
  console.log('Interaction changed:', type, value)
}

onMounted(() => {
  fetchRecommendations()
})
</script>

<style scoped>
.recommend-view {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header h1 {
  color: #e4e4e7;
  font-size: 28px;
}

.controls {
  display: flex;
  gap: 12px;
}

.loading {
  padding: 20px;
}

.empty {
  text-align: center;
  padding: 60px 20px;
  color: #71717a;
}

.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
}
</style>
