<template>
  <div class="book-detail" v-if="book">
    <div class="info-section">
      <div class="cover-area">
        <img v-if="book.image_url" :src="book.image_url" :alt="book.title" class="cover" />
        <div v-else class="no-cover">
          <el-icon :size="60"><Reading /></el-icon>
          <span>暂无封面</span>
        </div>
      </div>

      <div class="info">
        <h1 class="title">{{ book.title }}</h1>
        <div class="meta">
          <div class="meta-item">
            <el-icon><User /></el-icon>
            <span>{{ book.author || '未知作者' }}</span>
          </div>
          <div class="meta-item">
            <el-icon><OfficeBuilding /></el-icon>
            <span>{{ book.publisher || '未知出版社' }}</span>
          </div>
          <div v-if="book.year" class="meta-item">
            <el-icon><Calendar /></el-icon>
            <span>{{ book.year }} 年</span>
          </div>
          <div class="meta-item">
            <el-icon><CollectionTag /></el-icon>
            <span>ISBN: {{ book.isbn }}</span>
          </div>
        </div>

        <!-- 社区评分数据卡片 -->
        <div v-if="communityRating.rating_count > 0" class="community-card">
          <div class="community-header">
            <h3><el-icon><TrendCharts /></el-icon> 社区口碑</h3>
            <p class="hint">{{ communityRating.rating_count }} 位读者已评分，帮你做判断</p>
          </div>
          <div class="community-body">
            <div class="avg-score">
              <div class="score-num">{{ communityRating.avg_rating }}</div>
              <div class="score-label">平均评分</div>
              <div class="score-star">
                <el-rate
                  :model-value="Math.round(communityRating.avg_rating)"
                  disabled
                  show-score
                  text-color="#22d3ee"
                  :max="10"
                />
              </div>
            </div>
            <div class="distribution">
              <div class="dist-row" v-for="score in [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]" :key="score">
                <span class="dist-score">{{ score }}</span>
                <div class="dist-bar-wrap">
                  <div class="dist-bar" :style="{ width: getBarWidth(score) + '%' }"></div>
                </div>
                <span class="dist-count">{{ communityRating.distribution[String(score)] || 0 }}</span>
              </div>
            </div>
          </div>
          <div class="community-footer">
            <el-icon><InfoFilled /></el-icon>
            <span>最多人给了 <b>{{ communityRating.most_common_rating }}</b> 分，这本书整体口碑
              <b>{{ getRatingQuality(communityRating.avg_rating) }}</b></span>
          </div>
        </div>

        <!-- 没有社区数据的情况 -->
        <div v-else class="community-card empty">
          <div class="community-header">
            <h3><el-icon><Warning /></el-icon> 暂无评分数据</h3>
            <p class="hint">这本书还没有人评分，你可以成为第一个！</p>
          </div>
          <div class="community-footer">
            <el-icon><MagicStick /></el-icon>
            <span>评分后，系统会更了解你的口味，帮你发现更多好书</span>
          </div>
        </div>

        <!-- 你的评分 -->
        <div class="rating-section">
          <div class="rating-header">
            <h3><el-icon><Star /></el-icon> 你的评分</h3>
            <p class="hint" v-if="!hasUserRating">
              没看过也没关系！根据标题、作者和社区口碑，凭直觉打个分就好。
              评分会帮助推荐系统了解你的阅读偏好。
            </p>
            <p class="hint rated" v-else>
              你已给这本书 <b>{{ userRating }}</b> 分，可以随时修改。
            </p>
          </div>
          <div class="rating-control">
            <el-rate
              v-model="userRatingVal"
              :max="10"
              show-score
              text-color="#22d3ee"
              @change="handleRate"
            />
            <span class="rating-range">(1 - 10 分)</span>
          </div>
          <el-button v-if="!userStore.isLoggedIn" type="primary" @click="$router.push('/login')">
            <el-icon><UserFilled /></el-icon> 登录后评分
          </el-button>
          <div v-if="communityRating.rating_count > 0 && userRatingVal > 0" class="rating-compare">
            <el-icon>
              <component :is="getCompareIcon()" />
            </el-icon>
            <span>{{ getCompareText() }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="similarBooks.length > 0" class="similar-section">
      <div class="section-header">
        <h2><el-icon><MagicStick /></el-icon> 相似书籍推荐</h2>
        <span class="hint">同作者或同出版社</span>
      </div>
      <div class="book-grid">
        <BookCard v-for="b in similarBooks" :key="b.id" :book="b" />
      </div>
    </div>
  </div>

  <div v-else-if="!loading" class="empty-area">
    <el-empty description="未找到该书籍">
      <el-button type="primary" @click="$router.push('/')">返回书籍广场</el-button>
    </el-empty>
  </div>

  <div v-else class="loading-area">
    <el-progress type="dashboard" :percentage="75" :color="'#6366f1'" :stroke-width="10" :text-inside="true" />
    <p>加载中...</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  User, OfficeBuilding, Calendar, CollectionTag, Star, Reading,
  MagicStick, UserFilled, Warning, InfoFilled, TrendCharts,
  CaretTop, CaretBottom, Minus
} from '@element-plus/icons-vue'
import { bookAPI, ratingAPI } from '../api'
import { useUserStore } from '../stores/user'
import BookCard from '../components/BookCard.vue'

const route = useRoute()
const userStore = useUserStore()

const book = ref(null)

// 浏览器标签标题跟随书名
const updateTitle = (b) => {
  if (b && b.title) {
    document.title = `${b.title} - BookRec`
  } else {
    document.title = '书籍详情 - BookRec'
  }
}
const similarBooks = ref([])
const userRatingVal = ref(0)
const loading = ref(false)
const communityRating = ref({
  avg_rating: null,
  rating_count: 0,
  distribution: {},
  most_common_rating: null
})

const hasUserRating = computed(() => {
  if (!book.value || !book.value.community_rating) return false
  return book.value.community_rating.user_rating != null
})

const userRating = computed(() => {
  if (!book.value || !book.value.community_rating) return 0
  return book.value.community_rating.user_rating || 0
})

const fetchBook = async () => {
  loading.value = true
  try {
    const params = userStore.isLoggedIn ? { user_id: userStore.user.id } : {}
    const bookRes = await bookAPI.getBook(route.params.id, params)
    book.value = bookRes.book
    updateTitle(bookRes.book)

    // 提取社区评分
    if (book.value.community_rating) {
      communityRating.value = book.value.community_rating
    }

    // 设置用户已有的评分
    if (hasUserRating.value) {
      userRatingVal.value = userRating.value
    }

    const similarRes = await bookAPI.getSimilar(route.params.id)
    similarBooks.value = similarRes.similar_books || []
  } catch (err) {
    console.error('获取书籍详情失败:', err)
  } finally {
    loading.value = false
  }
}

const handleRate = async (val) => {
  if (!userStore.isLoggedIn) {
    ElMessage.warning('请先登录再评分')
    userRatingVal.value = 0
    return
  }
  try {
    await ratingAPI.createRating({
      user_id: userStore.user.id,
      book_id: book.value.id,
      rating: val
    })
    ElMessage.success(`已评分 ${val} 分，感谢你的反馈！`)
  } catch (err) {
    ElMessage.error('评分失败，请重试')
  }
}

const getBarWidth = (score) => {
  const total = communityRating.value.rating_count || 1
  const count = communityRating.value.distribution[String(score)] || 0
  return Math.max((count / total) * 100, 1)
}

const getRatingQuality = (avg) => {
  if (avg >= 9) return '非常优秀'
  if (avg >= 8) return '不错'
  if (avg >= 7) return '一般偏好'
  if (avg >= 6) return '评价一般'
  return '偏低'
}

const getCompareIcon = () => {
  const diff = userRatingVal.value - (communityRating.value.avg_rating || 0)
  if (diff > 1) return 'CaretTop'
  if (diff < -1) return 'CaretBottom'
  return 'Minus'
}

const getCompareText = () => {
  const diff = userRatingVal.value - (communityRating.value.avg_rating || 0)
  if (diff > 2) return `你比平均读者更喜欢这本书（+${diff.toFixed(1)} 分）`
  if (diff > 0) return `你的评价比平均水平略高（+${diff.toFixed(1)} 分）`
  if (diff < -2) return `你比平均读者更不喜欢这本书（${diff.toFixed(1)} 分）`
  if (diff < 0) return `你的评价比平均水平略低（${diff.toFixed(1)} 分）`
  return '你的评价和大多数读者一致'
}

onMounted(() => {
  fetchBook()
})
</script>

<style scoped>
.book-detail {
  padding: 0;
}

.info-section {
  display: flex;
  gap: 40px;
  padding: 40px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 16px;
  margin-bottom: 32px;
  backdrop-filter: blur(20px);
}

.cover-area {
  flex-shrink: 0;
  width: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cover {
  max-width: 100%;
  max-height: 340px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.no-cover {
  width: 100%;
  height: 340px;
  background-color: #1f1f28;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #52525b;
  gap: 12px;
  font-size: 14px;
}

.info {
  flex: 1;
  min-width: 0;
}

.title {
  color: #e4e4e7;
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 24px 0;
  line-height: 1.3;
}

.meta {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 28px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #a1a1aa;
  font-size: 15px;
}

.meta-item .el-icon {
  color: #71717a;
}

/* 社区评分卡片 */
.community-card {
  padding: 24px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  margin-bottom: 24px;
}

.community-card.empty {
  border-style: dashed;
  background: rgba(255,255,255,0.02);
}

.community-header {
  margin-bottom: 20px;
}

.community-header h3 {
  color: #6366f1;
  margin: 0 0 6px 0;
  font-size: 18px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.community-header .hint {
  color: #71717a;
  margin: 0;
  font-size: 13px;
}

.community-body {
  display: flex;
  gap: 32px;
  align-items: flex-start;
}

.avg-score {
  text-align: center;
  padding: 16px 20px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  min-width: 180px;
}

.score-num {
  font-size: 48px;
  font-weight: 800;
  color: #22d3ee;
  line-height: 1;
  margin-bottom: 8px;
}

.score-label {
  font-size: 12px;
  color: #71717a;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 8px;
}

.score-star {
  display: flex;
  justify-content: center;
}

.distribution {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dist-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.dist-score {
  width: 24px;
  text-align: right;
  color: #a1a1aa;
  font-weight: 500;
}

.dist-bar-wrap {
  flex: 1;
  height: 14px;
  background: rgba(255,255,255,0.05);
  border-radius: 3px;
  overflow: hidden;
}

.dist-bar {
  height: 100%;
  background: linear-gradient(90deg, #6366f1 0%, #22d3ee 100%);
  min-width: 2px;
  transition: width 0.3s ease;
}

.dist-count {
  width: 40px;
  text-align: right;
  color: #71717a;
  font-size: 12px;
}

.community-footer {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid rgba(255,255,255,0.07);
  display: flex;
  align-items: center;
  gap: 8px;
  color: #a1a1aa;
  font-size: 13px;
}

.community-footer b {
  color: #6366f1;
  font-weight: 600;
}

/* 用户评分卡片 */
.rating-section {
  padding: 24px;
  background-color: rgba(255,255,255,0.03);
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.07);
}

.rating-header {
  margin-bottom: 16px;
}

.rating-header h3 {
  color: #6366f1;
  margin: 0 0 6px 0;
  font-size: 18px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.rating-header .hint {
  color: #71717a;
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
}

.rating-header .hint.rated {
  color: #22d3ee;
  font-weight: 500;
}

.rating-control {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.rating-range {
  color: #52525b;
  font-size: 13px;
}

.rating-compare {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed rgba(255,255,255,0.07);
  display: flex;
  align-items: center;
  gap: 6px;
  color: #a1a1aa;
  font-size: 13px;
}

.similar-section {
  padding: 32px;
  background: rgba(255,255,255,0.02);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.section-header h2 {
  color: #e4e4e7;
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-header .hint {
  color: #52525b;
  font-size: 13px;
}

.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 20px;
}

.loading-area,
.empty-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px 20px;
  text-align: center;
  color: #71717a;
}

@media (max-width: 900px) {
  .info-section {
    flex-direction: column;
    align-items: center;
    padding: 24px;
  }
  .cover-area {
    width: 100%;
    max-width: 240px;
  }
  .community-body {
    flex-direction: column;
  }
  .avg-score {
    width: 100%;
    min-width: 0;
  }
}
</style>
