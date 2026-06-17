<template>
  <div class="home-view">
    <!-- 顶部搜索栏 -->
    <div class="header">
      <h1>📚 书籍广场</h1>
      <div class="search-area">
        <el-autocomplete
          v-model="searchQuery"
          :fetch-suggestions="fetchSuggestions"
          placeholder="搜索书名或作者..."
          class="search-input"
          clearable
          :trigger-on-focus="false"
          :hide-loading="true"
          @select="handleSuggestionSelect"
          @input="debouncedSearch"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
          <template #default="{ item }">
            <div class="suggestion-item">
              <el-icon v-if="item.type === 'title'" class="suggestion-icon"><Document /></el-icon>
              <el-icon v-else class="suggestion-icon"><User /></el-icon>
              <span v-html="highlightText(item.text, searchQuery)"></span>
              <span class="suggestion-type">{{ item.type === 'title' ? '书名' : '作者' }}</span>
            </div>
          </template>
        </el-autocomplete>
        <el-button type="primary" @click="handleSearch" class="search-btn">
          <el-icon><Search /></el-icon> 搜索
        </el-button>
      </div>
    </div>

    <!-- 筛选和内容区域 -->
    <div class="content-area">
      <!-- 侧边栏筛选面板 -->
      <div class="sidebar" :class="{ collapsed: sidebarCollapsed }">
        <div class="sidebar-header">
          <span v-if="!sidebarCollapsed"><el-icon><Filter /></el-icon> 筛选</span>
          <el-button text @click="sidebarCollapsed = !sidebarCollapsed">
            <el-icon>
              <ArrowLeft v-if="!sidebarCollapsed" />
              <ArrowRight v-else />
            </el-icon>
          </el-button>
        </div>

        <div v-if="!sidebarCollapsed" class="sidebar-content">
          <!-- 排序选项 -->
          <div class="filter-section">
            <h4><el-icon><Sort /></el-icon> 排序</h4>
            <el-select v-model="currentSort" placeholder="选择排序方式" @change="handleSortChange">
              <el-option label="综合排序" value="default" />
              <el-option label="评分最高" value="rating_desc" />
              <el-option label="评分最低" value="rating_asc" />
              <el-option label="评价最多" value="reviews_desc" />
              <el-option label="最新出版" value="year_desc" />
              <el-option label="最旧出版" value="year_asc" />
              <el-option label="热门推荐" value="popularity" />
            </el-select>
          </div>

          <!-- 类别筛选 -->
          <div class="filter-section">
            <h4><el-icon><Collection /></el-icon> 类别</h4>
            <el-checkbox-group v-model="selectedCategories" @change="handleFilterChange">
              <el-checkbox v-for="cat in availableCategories" :key="cat" :label="cat">
                {{ cat }}
              </el-checkbox>
            </el-checkbox-group>
          </div>

          <!-- 评分区间筛选 -->
          <div class="filter-section">
            <h4><el-icon><StarFilled /></el-icon> 评分区间</h4>
            <el-radio-group v-model="ratingRange" @change="handleFilterChange">
              <el-radio label="">不限</el-radio>
              <el-radio label="8-10">8-10分</el-radio>
              <el-radio label="6-8">6-8分</el-radio>
              <el-radio label="4-6">4-6分</el-radio>
              <el-radio label="0-4">4分以下</el-radio>
            </el-radio-group>
          </div>

          <!-- 年份范围筛选 -->
          <div class="filter-section">
            <h4><el-icon><Calendar /></el-icon> 出版年份</h4>
            <el-input-number v-model="yearFrom" :min="1900" :max="2024" placeholder="起始年" @change="handleFilterChange" />
            <span class="year-separator">至</span>
            <el-input-number v-model="yearTo" :min="1900" :max="2024" placeholder="结束年" @change="handleFilterChange" />
          </div>

          <!-- 作者筛选 -->
          <div class="filter-section">
            <h4><el-icon><User /></el-icon> 作者</h4>
            <el-input v-model="authorFilter" placeholder="输入作者名" clearable @change="handleFilterChange" />
          </div>

          <!-- 清除筛选按钮 -->
          <el-button type="danger" text @click="clearAllFilters" class="clear-btn">
            <el-icon><Delete /></el-icon> 清除所有筛选
          </el-button>
        </div>
      </div>

      <!-- 主内容区域 -->
      <div class="main-content">
        <!-- 热门搜索和搜索历史 -->
        <div v-if="!searchQuery && activeFilterCount === 0" class="hot-search-section">
          <div class="hot-search">
            <h3><el-icon><TrendCharts /></el-icon> 热门搜索</h3>
            <div class="hot-tags">
              <el-tag
                v-for="term in hotSearchTerms"
                :key="term"
                class="hot-tag"
                @click="handleHotSearch(term)"
              >
                🔥 {{ term }}
              </el-tag>
            </div>
          </div>

          <div v-if="userStore.isLoggedIn && searchHistory.length > 0" class="search-history">
            <h3><el-icon><Clock /></el-icon> 搜索历史</h3>
            <div class="history-tags">
              <el-tag
                v-for="term in searchHistory"
                :key="term"
                class="history-tag"
                closable
                @close="removeHistoryItem(term)"
                @click="handleHotSearch(term)"
              >
                {{ term }}
              </el-tag>
            </div>
            <el-button type="danger" text size="small" @click="clearHistory">
              <el-icon><Delete /></el-icon> 清除历史
            </el-button>
          </div>
        </div>

        <!-- 筛选结果统计和标签 -->
        <div v-if="activeFilterCount > 0 || searchQuery" class="filter-info">
          <div class="result-count">
            找到 <span class="count-number">{{ total }}</span> 本书籍
          </div>
          <div class="active-filters">
            <el-tag
              v-if="searchQuery"
              closable
              @close="clearSearch"
              class="filter-tag"
            >
              搜索: {{ searchQuery }}
            </el-tag>
            <el-tag
              v-for="cat in selectedCategories"
              :key="cat"
              closable
              @close="removeCategory(cat)"
              class="filter-tag"
            >
              类别: {{ cat }}
            </el-tag>
            <el-tag
              v-if="ratingRange"
              closable
              @close="ratingRange = ''"
              class="filter-tag"
            >
              评分: {{ ratingRange }}分
            </el-tag>
            <el-tag
              v-if="yearFrom || yearTo"
              closable
              @close="clearYearFilter"
              class="filter-tag"
            >
              年份: {{ yearFrom || '...' }} - {{ yearTo || '...' }}
            </el-tag>
            <el-tag
              v-if="authorFilter"
              closable
              @close="authorFilter = ''"
              class="filter-tag"
            >
              作者: {{ authorFilter }}
            </el-tag>
          </div>
        </div>

        <!-- 骨架屏加载 -->
        <div v-if="loading" class="skeleton-grid">
          <div v-for="i in 12" :key="i" class="skeleton-card">
            <div class="skeleton-cover skeleton-pulse"></div>
            <div class="skeleton-info">
              <div class="skeleton-title skeleton-pulse"></div>
              <div class="skeleton-author skeleton-pulse"></div>
              <div class="skeleton-rating skeleton-pulse"></div>
            </div>
          </div>
        </div>

        <div v-else-if="books.length === 0" class="empty-area">
          <el-empty :description="emptyDescription">
            <template #image>
              <div class="empty-icon">📖</div>
            </template>
            <el-button v-if="activeFilterCount > 0" type="primary" @click="clearAllFilters">
              清除筛选条件
            </el-button>
          </el-empty>
        </div>

        <template v-else>
          <!-- 书籍列表：books.length > 40 时启用虚拟滚动，否则使用普通渲染 -->
          <VirtualBookList
            v-if="books.length > 40"
            :books="books"
            :item-height="280"
            :item-width="200"
            :gap="20"
            :buffer="3"
            :search-keyword="searchQuery"
            @click-book="goToBook"
          />

          <div v-else class="book-grid">
            <BookCard
              v-for="book in books"
              :key="book.id"
              :book="book"
              :search-keyword="searchQuery"
              @click="goToBook(book)"
            />
          </div>

          <div v-if="total > pageSize" class="pagination">
            <el-pagination
              v-model:current-page="currentPage"
              :page-size="pageSize"
              :total="total"
              layout="prev, pager, next, jumper"
              background
              @current-change="handlePageChange"
            />
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Search, Reading, User, StarFilled, Histogram, Trophy, Calendar,
  Filter, Sort, Collection, Delete, Clock, TrendCharts,
  Document, ArrowLeft, ArrowRight
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { bookAPI } from '../api'
import BookCard from '../components/BookCard.vue'
import VirtualBookList from '../components/VirtualBookList.vue'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()

// 搜索相关
const searchQuery = ref('')
const suggestions = ref([])
let searchTimer = null
let suggestionTimer = null

// 书籍数据
const books = ref([])
const hotBooks = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const loading = ref(false)

// 筛选相关
const sidebarCollapsed = ref(false)
const currentSort = ref('default')
const selectedCategories = ref([])
const ratingRange = ref('')
const yearFrom = ref(null)
const yearTo = ref(null)
const authorFilter = ref('')
const availableCategories = ref([])

// 搜索历史和热门搜索
const searchHistory = ref([])
const hotSearchTerms = ref([])

// 图表相关
const ratingDistRef = ref(null)
const topAuthorsRef = ref(null)
const timelineRef = ref(null)
let ratingDistChart = null
let topAuthorsChart = null
let timelineChart = null

const ORANGE = '#F97316'
const ORANGE_LIGHT = '#fb923c'
const BLUE = '#3b82f6'
const GREEN = '#10b981'
const PURPLE = '#8b5cf6'
const GRID_LINE = '#e2e8f0'
const TEXT_COLOR = '#475569'

// 计算活跃筛选数量
const activeFilterCount = computed(() => {
  let count = 0
  if (searchQuery.value) count++
  if (selectedCategories.value.length) count += selectedCategories.value.length
  if (ratingRange.value) count++
  if (yearFrom.value || yearTo.value) count++
  if (authorFilter.value) count++
  return count
})

// 空状态描述
const emptyDescription = computed(() => {
  if (activeFilterCount.value > 0) {
    return '没有找到符合条件的书籍'
  }
  return '暂无书籍数据，请先导入 Book-Crossing 数据集'
})

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
    return safeText.replace(regex, '<mark class="highlight">$1</mark>')
  } catch {
    return safeText
  }
}

// 构建查询参数
const buildQueryParams = () => {
  const params = {
    page: currentPage.value,
    per_page: pageSize,
    sort: currentSort.value
  }

  if (searchQuery.value && searchQuery.value.trim()) {
    params.search = searchQuery.value.trim()
  }

  if (selectedCategories.value.length > 0) {
    params.category = selectedCategories.value.join(',')
  }

  if (ratingRange.value) {
    const [min, max] = ratingRange.value.split('-')
    params.min_rating = min
    params.max_rating = max
  }

  if (yearFrom.value) {
    params.year_from = yearFrom.value
  }

  if (yearTo.value) {
    params.year_to = yearTo.value
  }

  if (authorFilter.value && authorFilter.value.trim()) {
    params.author = authorFilter.value.trim()
  }

  return params
}

// 获取书籍列表
const fetchBooks = async () => {
  loading.value = true
  try {
    const params = buildQueryParams()
    const res = await bookAPI.getBooks(params)
    books.value = res.books || []
    total.value = res.total || 0
  } catch (err) {
    console.error('加载书籍失败:', err)
    ElMessage.error('加载书籍失败')
  } finally {
    loading.value = false
  }
}

// 获取热门书籍（轮播图）
const fetchHotBooks = async () => {
  try {
    const res = await bookAPI.getBooks({ page: 1, per_page: 8, sort: 'popular' })
    hotBooks.value = res.books?.slice(0, 6) || []
  } catch (err) {
    console.error('加载热门书籍失败:', err)
    hotBooks.value = []
  }
}

// 获取筛选选项
const fetchFilterOptions = async () => {
  try {
    const res = await bookAPI.getFilterOptions()
    if (res.categories) {
      availableCategories.value = res.categories.slice(0, 20) // 限制显示数量
    }
  } catch (err) {
    console.error('获取筛选选项失败:', err)
  }
}

// 获取热门搜索词
const fetchHotSearch = async () => {
  try {
    const res = await bookAPI.getHotSearch()
    hotSearchTerms.value = res.hot_search || []
  } catch (err) {
    console.error('获取热门搜索失败:', err)
  }
}

// 获取搜索历史
const fetchSearchHistory = async () => {
  if (!userStore.isLoggedIn) return
  try {
    const res = await bookAPI.getSearchHistory()
    searchHistory.value = res.history || []
  } catch (err) {
    // 401 等认证问题由拦截器统一处理，此处静默处理
    if (err?.response?.status !== 401) {
      console.error('获取搜索历史失败:', err)
    }
  }
}

// 添加搜索历史
const addSearchHistory = async (term) => {
  if (!userStore.isLoggedIn || !term) return
  try {
    await bookAPI.addSearchHistory(term)
    await fetchSearchHistory()
  } catch (err) {
    if (err?.response?.status !== 401) {
      console.error('添加搜索历史失败:', err)
    }
  }
}

// 清除搜索历史
const clearHistory = async () => {
  if (!userStore.isLoggedIn) return
  try {
    await bookAPI.clearSearchHistory()
    searchHistory.value = []
  } catch (err) {
    if (err?.response?.status !== 401) {
      console.error('清除搜索历史失败:', err)
    }
  }
}

// 移除单条历史记录
const removeHistoryItem = (term) => {
  searchHistory.value = searchHistory.value.filter(t => t !== term)
}

// 获取搜索建议
const fetchSuggestions = async (query, callback) => {
  if (!query || query.length < 1) {
    callback([])
    return
  }

  if (suggestionTimer) clearTimeout(suggestionTimer)
  suggestionTimer = setTimeout(async () => {
    try {
      const res = await bookAPI.getSuggestions(query, 10)
      callback(res.suggestions || [])
    } catch (err) {
      console.error('获取搜索建议失败:', err)
      callback([])
    }
  }, 200)
}

// 处理建议项选择
const handleSuggestionSelect = (item) => {
  searchQuery.value = item.text
  handleSearch()
}

// 搜索建议定时器
const debouncedSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    fetchBooks()
  }, 400)
}

// 处理搜索
const handleSearch = () => {
  currentPage.value = 1
  fetchBooks()
  if (searchQuery.value) {
    addSearchHistory(searchQuery.value)
  }
}

// 处理热门搜索词点击
const handleHotSearch = (term) => {
  searchQuery.value = term
  handleSearch()
}

// 处理排序变更
const handleSortChange = () => {
  currentPage.value = 1
  fetchBooks()
}

// 处理筛选变更
const handleFilterChange = () => {
  currentPage.value = 1
  fetchBooks()
}

// 清除搜索
const clearSearch = () => {
  searchQuery.value = ''
  currentPage.value = 1
  fetchBooks()
}

// 移除类别筛选
const removeCategory = (cat) => {
  selectedCategories.value = selectedCategories.value.filter(c => c !== cat)
  fetchBooks()
}

// 清除年份筛选
const clearYearFilter = () => {
  yearFrom.value = null
  yearTo.value = null
  fetchBooks()
}

// 清除所有筛选
const clearAllFilters = () => {
  searchQuery.value = ''
  selectedCategories.value = []
  ratingRange.value = ''
  yearFrom.value = null
  yearTo.value = null
  authorFilter.value = ''
  currentSort.value = 'default'
  currentPage.value = 1
  fetchBooks()
}

// 分页变更
const handlePageChange = (page) => {
  currentPage.value = page
  fetchBooks()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// 跳转到书籍详情（支持 book 对象 或 book id）
const goToBook = (book) => {
  const id = typeof book === 'object' && book !== null ? book.id : book
  if (id) router.push(`/book/${id}`)
}

// 初始化图表
const initCharts = () => {
  if (ratingDistRef.value) ratingDistChart = echarts.init(ratingDistRef.value)
  if (topAuthorsRef.value) topAuthorsChart = echarts.init(topAuthorsRef.value)
  if (timelineRef.value) timelineChart = echarts.init(timelineRef.value)
  updateCharts()
}

const updateCharts = () => {
  updateRatingDistChart()
  updateTopAuthorsChart()
  updateTimelineChart()
}

const updateRatingDistChart = () => {
  if (!ratingDistChart) return
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#e2e8f0',
      textStyle: { color: '#1e293b' },
      formatter: '{b}: {c} 本书'
    },
    grid: { left: '5%', right: '5%', bottom: '10%', top: '5%', containLabel: true },
    xAxis: {
      type: 'category',
      data: ['0-2', '2-4', '4-6', '6-8', '8-10'],
      axisLabel: { color: TEXT_COLOR, fontSize: 12 },
      axisLine: { lineStyle: { color: GRID_LINE } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '书籍数量',
      nameTextStyle: { color: TEXT_COLOR },
      axisLabel: { color: TEXT_COLOR },
      axisLine: { lineStyle: { color: GRID_LINE } },
      splitLine: { lineStyle: { color: GRID_LINE, type: 'dashed' } }
    },
    series: [{
      type: 'bar',
      barWidth: '50%',
      data: [
        { value: 120, itemStyle: { color: '#ef4444' } },
        { value: 280, itemStyle: { color: '#f97316' } },
        { value: 520, itemStyle: { color: '#eab308' } },
        { value: 680, itemStyle: { color: '#22c55e' } },
        { value: 380, itemStyle: { color: '#10b981' } }
      ],
      label: {
        show: true,
        position: 'top',
        color: TEXT_COLOR,
        fontSize: 12,
        formatter: '{c}'
      },
      itemStyle: { borderRadius: [4, 4, 0, 0] }
    }]
  }
  ratingDistChart.setOption(option)
}

const updateTopAuthorsChart = () => {
  if (!topAuthorsChart) return
  const authors = [
    'J.K. Rowling', 'Stephen King', 'Agatha Christie', 'Haruki Murakami',
    'Jane Austen', 'George Orwell', 'Leo Tolstoy', 'Mark Twain',
    'Charles Dickens', 'Oscar Wilde'
  ]
  const ratings = [9.2, 8.9, 8.7, 8.5, 8.4, 8.3, 8.2, 8.1, 8.0, 7.9]

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#ffffff',
      borderColor: '#e2e8f0',
      textStyle: { color: '#1e293b' },
      formatter: (params) => {
        const p = params[0]
        return `${p.name}<br/>评分: ${p.value}`
      }
    },
    grid: { left: '3%', right: '8%', bottom: '3%', top: '3%', containLabel: true },
    xAxis: {
      type: 'value',
      name: '评分',
      min: 0,
      max: 10,
      nameTextStyle: { color: TEXT_COLOR },
      axisLabel: { color: TEXT_COLOR },
      axisLine: { lineStyle: { color: GRID_LINE } },
      splitLine: { lineStyle: { color: GRID_LINE, type: 'dashed' } }
    },
    yAxis: {
      type: 'category',
      data: authors.reverse(),
      axisLabel: { color: TEXT_COLOR, fontSize: 11 },
      axisLine: { lineStyle: { color: GRID_LINE } },
      axisTick: { show: false }
    },
    series: [{
      type: 'bar',
      barWidth: '60%',
      data: ratings.reverse(),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: ORANGE },
          { offset: 1, color: ORANGE_LIGHT }
        ]),
        borderRadius: [0, 4, 4, 0]
      },
      label: {
        show: true,
        position: 'right',
        color: ORANGE,
        fontSize: 11,
        fontWeight: 600,
        formatter: '{c}'
      }
    }]
  }
  topAuthorsChart.setOption(option)
}

const updateTimelineChart = () => {
  if (!timelineChart) return
  const months = ['1月', '2月', '3月', '4月', '5月', '6月']
  const newBooks = [45, 62, 78, 55, 89, 102]
  const recommendations = [120, 145, 188, 165, 210, 256]

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#e2e8f0',
      textStyle: { color: '#1e293b' },
      formatter: (params) => {
        let out = params[0].axisValue + '<br/>'
        for (const p of params) {
          out += `${p.marker} ${p.seriesName}: ${p.value}<br/>`
        }
        return out
      }
    },
    legend: {
      data: ['新书入库', '推荐次数'],
      textStyle: { color: TEXT_COLOR },
      top: 10,
      right: 20
    },
    grid: { left: '5%', right: '5%', bottom: '10%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { color: TEXT_COLOR, fontSize: 12 },
      axisLine: { lineStyle: { color: GRID_LINE } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '数量',
      nameTextStyle: { color: TEXT_COLOR },
      axisLabel: { color: TEXT_COLOR },
      axisLine: { lineStyle: { color: GRID_LINE } },
      splitLine: { lineStyle: { color: GRID_LINE, type: 'dashed' } }
    },
    series: [
      {
        name: '新书入库',
        type: 'bar',
        barWidth: '30%',
        data: newBooks,
        itemStyle: { color: BLUE },
        barGap: '20%'
      },
      {
        name: '推荐次数',
        type: 'bar',
        barWidth: '30%',
        data: recommendations,
        itemStyle: { color: GREEN },
        barGap: '20%'
      }
    ]
  }
  timelineChart.setOption(option)
}

const handleResize = () => {
  ratingDistChart?.resize()
  topAuthorsChart?.resize()
  timelineChart?.resize()
}

onMounted(() => {
  fetchBooks()
  fetchHotBooks()
  fetchFilterOptions()
  fetchHotSearch()
  fetchSearchHistory()
  setTimeout(initCharts, 100)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
  if (suggestionTimer) clearTimeout(suggestionTimer)
  ratingDistChart?.dispose()
  topAuthorsChart?.dispose()
  timelineChart?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
/* ============================================
   极客极客美学 - 书籍广场全局样式
   ============================================ */

.home-view {
  background: var(--bg-primary, #f8fafc);
  color: var(--text-primary, #1e293b);
  min-height: 100vh;
  font-family: 'DM Sans', sans-serif;
  animation: pageFadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes pageFadeIn {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ============================================
   顶部搜索栏
   ============================================ */

.header {
  background: var(--bg-card, #ffffff);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  backdrop-filter: blur(20px);
  padding: 28px 40px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
}

.header h1 {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 28px;
  font-weight: 700;
  margin: 0;
  background: linear-gradient(135deg, #dbeafe 0%, #3b82f6 50%, #0891b2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  display: flex;
  align-items: center;
  gap: 10px;
}

.header .subtitle {
  color: var(--text-secondary, #475569);
  font-size: 13px;
  margin-top: 4px;
  font-weight: 400;
}

.search-area {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  width: 320px;
}

/* ============================================
   Element Plus 输入框覆盖 - 玻璃态
   ============================================ */

:deep(.el-input__wrapper) {
  background: var(--bg-secondary, #f1f5f9) !important;
  border: 1px solid var(--border-color, #e2e8f0) !important;
  box-shadow: none !important;
  border-radius: 12px !important;
  padding: 10px 16px;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

:deep(.el-input__wrapper:hover) {
  border-color: rgba(37, 99, 235, 0.4) !important;
  background: var(--border-color, #e2e8f0) !important;
}

:deep(.el-input__wrapper.is-focus) {
  border-color: var(--accent, #2563eb) !important;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15) !important;
  background: var(--border-color, #e2e8f0) !important;
}

:deep(.el-input__inner) {
  color: var(--text-primary, #1e293b) !important;
  font-family: 'DM Sans', sans-serif;
}

:deep(.el-input__inner::placeholder) {
  color: var(--text-muted, #94a3b8) !important;
}

:deep(.el-input__prefix) {
  color: var(--text-secondary, #475569);
}

/* Autocomplete 下拉建议 */
:deep(.el-autocomplete-suggestion) {
  background: var(--bg-card, #ffffff) !important;
  border: 1px solid var(--border-color, #e2e8f0) !important;
  border-radius: 12px !important;
  overflow: hidden;
}

:deep(.el-autocomplete-suggestion li) {
  color: var(--text-primary, #1e293b) !important;
  padding: 10px 14px;
}

:deep(.el-autocomplete-suggestion li:hover) {
  background: rgba(37, 99, 235, 0.15) !important;
}

/* 搜索建议项 */
.suggestion-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}

.suggestion-icon {
  color: var(--accent, #2563eb);
  flex-shrink: 0;
}

.suggestion-type {
  margin-left: auto;
  color: var(--text-secondary, #475569);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

:deep(.highlight) {
  background-color: rgba(37, 99, 235, 0.2);
  color: var(--accent-light, #3b82f6);
  padding: 0 2px;
  border-radius: 3px;
}

/* 搜索按钮 */
.search-btn {
  background: linear-gradient(135deg, #2563eb, #0891b2) !important;
  border: none !important;
  border-radius: 12px !important;
  font-family: 'DM Sans', sans-serif;
  font-weight: 600;
  padding: 10px 20px;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.search-btn:hover {
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.3) !important;
  transform: translateY(-2px);
  background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
}

/* ============================================
   内容区域布局
   ============================================ */

.content-area {
  display: flex;
  gap: 0;
  padding: 0;
}

/* ============================================
   筛选侧边栏 - 玻璃态
   ============================================ */

.sidebar {
  width: 260px;
  flex-shrink: 0;
  background: var(--bg-card, #ffffff);
  border-right: 1px solid var(--border-color, #e2e8f0);
  padding: 24px 16px;
  min-height: calc(100vh - 120px);
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.sidebar.collapsed {
  width: 60px;
  padding: 24px 8px;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 8px 16px;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  margin-bottom: 20px;
  font-weight: 600;
  color: var(--text-primary, #1e293b);
  font-family: 'Space Grotesk', sans-serif;
}

.sidebar-header span {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sidebar-header .el-icon {
  color: var(--accent, #2563eb);
}

.sidebar-content {
  max-height: calc(100vh - 280px);
  overflow-y: auto;
  padding-right: 4px;
}

.sidebar-content::-webkit-scrollbar {
  width: 4px;
}

.sidebar-content::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar-content::-webkit-scrollbar-thumb {
  background: var(--border-color, #e2e8f0);
  border-radius: 2px;
}

.sidebar-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted, #94a3b8);
}

/* 筛选区块 */
.filter-section {
  margin-bottom: 28px;
  animation: sectionFadeIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) backwards;
}

.filter-section:nth-child(1) { animation-delay: 0.05s; }
.filter-section:nth-child(2) { animation-delay: 0.1s; }
.filter-section:nth-child(3) { animation-delay: 0.15s; }
.filter-section:nth-child(4) { animation-delay: 0.2s; }
.filter-section:nth-child(5) { animation-delay: 0.25s; }

@keyframes sectionFadeIn {
  from {
    opacity: 0;
    transform: translateX(-8px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.filter-section h4 {
  color: var(--text-muted, #94a3b8);
  font-family: 'Space Grotesk', sans-serif;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1.2px;
  font-weight: 600;
  margin: 0 0 14px 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-section h4 .el-icon {
  color: var(--accent, #2563eb);
  font-size: 12px;
}

/* Element Plus Select 覆盖 */
.filter-section :deep(.el-select) {
  width: 100%;
}

.filter-section :deep(.el-select__wrapper) {
  background: var(--bg-secondary, #f1f5f9) !important;
  border: 1px solid var(--border-color, #e2e8f0) !important;
  box-shadow: none !important;
  border-radius: 10px !important;
  min-height: 38px;
  font-family: 'DM Sans', sans-serif;
  color: var(--text-primary, #1e293b) !important;
}

.filter-section :deep(.el-select__wrapper:hover) {
  border-color: rgba(37, 99, 235, 0.4) !important;
}

.filter-section :deep(.el-select__wrapper.is-focused) {
  border-color: var(--accent, #2563eb) !important;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15) !important;
}

.filter-section :deep(.el-select__placeholder) {
  color: var(--text-secondary, #475569) !important;
}

.filter-section :deep(.el-select-dropdown) {
  background: var(--bg-card, #ffffff) !important;
  border: 1px solid var(--border-color, #e2e8f0) !important;
  border-radius: 10px !important;
  overflow: hidden;
}

.filter-section :deep(.el-select-dropdown__item) {
  color: var(--text-primary, #1e293b) !important;
  font-family: 'DM Sans', sans-serif;
}

.filter-section :deep(.el-select-dropdown__item.hover),
.filter-section :deep(.el-select-dropdown__item:hover) {
  background: rgba(37, 99, 235, 0.15) !important;
}

.filter-section :deep(.el-select-dropdown__item.is-selected) {
  background: rgba(37, 99, 235, 0.2) !important;
  color: var(--accent-light, #3b82f6) !important;
  font-weight: 600;
}

/* Element Plus Checkbox 覆盖 */
.filter-section :deep(.el-checkbox-group) {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.filter-section :deep(.el-checkbox) {
  --el-checkbox-text-color: var(--text-secondary, #475569);
  --el-checkbox-border-color: var(--border-color, #e2e8f0);
  --el-checkbox-bg-color: var(--bg-secondary, #f1f5f9);
  margin-right: 0;
}

.filter-section :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background: linear-gradient(135deg, #2563eb, #0891b2) !important;
  border-color: var(--accent, #2563eb) !important;
}

.filter-section :deep(.el-checkbox__input.is-checked + .el-checkbox__label) {
  color: var(--text-primary, #1e293b) !important;
}

.filter-section :deep(.el-checkbox__inner) {
  background: var(--bg-secondary, #f1f5f9) !important;
  border-color: var(--border-color, #e2e8f0) !important;
  border-radius: 4px;
}

.filter-section :deep(.el-checkbox__inner:hover) {
  border-color: rgba(37, 99, 235, 0.5) !important;
}

/* Element Plus Radio 覆盖 */
.filter-section :deep(.el-radio-group) {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.filter-section :deep(.el-radio) {
  --el-radio-text-color: var(--text-secondary, #475569);
  --el-radio-border-color: var(--border-color, #e2e8f0);
  margin-right: 0;
}

.filter-section :deep(.el-radio__input.is-checked .el-radio__inner) {
  background: linear-gradient(135deg, #2563eb, #0891b2) !important;
  border-color: var(--accent, #2563eb) !important;
}

.filter-section :deep(.el-radio__input.is-checked + .el-radio__label) {
  color: var(--text-primary, #1e293b) !important;
}

.filter-section :deep(.el-radio__inner) {
  background: var(--bg-secondary, #f1f5f9) !important;
  border-color: var(--border-color, #e2e8f0) !important;
}

.filter-section :deep(.el-radio__inner:hover) {
  border-color: rgba(37, 99, 235, 0.5) !important;
}

/* Element Plus InputNumber 覆盖 */
.filter-section :deep(.el-input-number) {
  width: 100%;
}

.filter-section :deep(.el-input-number .el-input__wrapper) {
  background: var(--bg-secondary, #f1f5f9) !important;
  border: 1px solid var(--border-color, #e2e8f0) !important;
  border-radius: 10px !important;
}

.filter-section :deep(.el-input-number__decrease),
.filter-section :deep(.el-input-number__increase) {
  background: var(--bg-secondary, #f1f5f9) !important;
  border-color: var(--border-color, #e2e8f0) !important;
  color: var(--text-secondary, #475569);
}

.filter-section :deep(.el-input-number__decrease:hover),
.filter-section :deep(.el-input-number__increase:hover) {
  color: var(--accent, #2563eb) !important;
}

/* Element Plus Input 覆盖 */
.filter-section :deep(.el-input) {
  width: 100%;
}

.year-separator {
  color: var(--text-muted, #94a3b8);
  margin: 0 8px;
  font-size: 12px;
}

/* 清除按钮 */
.clear-btn {
  width: 100%;
  margin-top: 8px;
  color: var(--text-muted, #94a3b8) !important;
  font-family: 'DM Sans', sans-serif;
}

.clear-btn:hover {
  color: #ef4444 !important;
}

/* ============================================
   主内容区域
   ============================================ */

.main-content {
  flex: 1;
  min-width: 0;
  padding: 28px 32px;
}

/* 热门搜索和历史 */
.hot-search-section {
  display: flex;
  gap: 32px;
  margin-bottom: 28px;
  padding: 24px;
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 16px;
  animation: sectionFadeIn 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}

.hot-search,
.search-history {
  flex: 1;
}

.hot-search h3,
.search-history h3 {
  color: var(--text-primary, #1e293b);
  font-size: 14px;
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 600;
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.hot-search h3 .el-icon,
.search-history h3 .el-icon {
  color: var(--accent, #2563eb);
}

.hot-tags,
.history-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hot-tag,
.history-tag {
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  background: rgba(37, 99, 235, 0.1) !important;
  border: 1px solid rgba(37, 99, 235, 0.2) !important;
  color: var(--accent-light, #3b82f6) !important;
  border-radius: 8px !important;
  padding: 6px 14px;
  font-size: 13px;
  font-family: 'DM Sans', sans-serif;
}

.hot-tag:hover,
.history-tag:hover {
  background: rgba(37, 99, 235, 0.2) !important;
  border-color: rgba(37, 99, 235, 0.4) !important;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
}

/* 筛选结果信息 */
.filter-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 18px 22px;
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 14px;
  animation: sectionFadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.result-count {
  color: var(--text-muted, #94a3b8);
  font-size: 14px;
}

.count-number {
  color: var(--accent, #2563eb);
  font-weight: 700;
  font-size: 20px;
  font-family: 'Space Grotesk', sans-serif;
}

.active-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-tag {
  background: rgba(37, 99, 235, 0.12) !important;
  border: 1px solid rgba(37, 99, 235, 0.25) !important;
  color: var(--accent-light, #3b82f6) !important;
  border-radius: 8px !important;
  padding: 4px 12px;
  font-size: 12px;
  font-family: 'DM Sans', sans-serif;
}

/* ============================================
   书籍网格 - 4列布局
   ============================================ */

.book-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(220px, 1fr));
  gap: 16px;
}

/* 骨架屏样式 */
.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(220px, 1fr));
  gap: 16px;
}

.skeleton-card {
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 12px;
  overflow: hidden;
}

.skeleton-cover {
  height: 200px;
  background: var(--bg-secondary, #f1f5f9);
}

.skeleton-info {
  padding: 16px;
}

.skeleton-title {
  height: 18px;
  background: var(--bg-secondary, #f1f5f9);
  border-radius: 4px;
  margin-bottom: 10px;
  width: 80%;
}

.skeleton-author {
  height: 12px;
  background: var(--bg-secondary, #f1f5f9);
  border-radius: 4px;
  margin-bottom: 12px;
  width: 60%;
}

.skeleton-rating {
  height: 16px;
  background: var(--bg-secondary, #f1f5f9);
  border-radius: 4px;
  width: 40%;
}

.skeleton-pulse {
  animation: skeletonPulse 1.5s ease-in-out infinite;
}

@keyframes skeletonPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 空状态 */
.empty-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 100px 20px;
  text-align: center;
}

.empty-icon {
  font-size: 72px;
  opacity: 0.4;
  margin-bottom: 20px;
}

/* ============================================
   Element Plus 分页 - 玻璃态按钮
   ============================================ */

:deep(.el-pagination) {
  justify-content: center;
  margin-top: 40px;
  margin-bottom: 40px;
  gap: 8px;
}

:deep(.el-pager) {
  gap: 6px;
}

:deep(.el-pager li) {
  background: var(--bg-secondary, #f1f5f9) !important;
  border: 1px solid var(--border-color, #e2e8f0) !important;
  color: var(--text-muted, #94a3b8) !important;
  border-radius: 8px !important;
  min-width: 36px;
  height: 36px;
  line-height: 36px;
  font-family: 'DM Sans', sans-serif;
  font-weight: 500;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

:deep(.el-pager li:hover) {
  background: rgba(37, 99, 235, 0.15) !important;
  border-color: rgba(37, 99, 235, 0.3) !important;
  color: var(--text-primary, #1e293b) !important;
}

:deep(.el-pager li.is-active) {
  background: linear-gradient(135deg, #2563eb, #0891b2) !important;
  color: #fff !important;
  border-color: transparent !important;
  font-weight: 600;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.25);
}

:deep(.el-pager li.is-disabled) {
  background: var(--bg-card, #ffffff) !important;
  color: var(--text-muted, #94a3b8) !important;
  border-color: var(--bg-secondary, #f1f5f9) !important;
}

:deep(.el-pagination button) {
  background: var(--bg-secondary, #f1f5f9) !important;
  border: 1px solid var(--border-color, #e2e8f0) !important;
  color: var(--text-muted, #94a3b8) !important;
  border-radius: 8px !important;
  min-width: 36px;
  height: 36px;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

:deep(.el-pagination button:hover) {
  background: rgba(37, 99, 235, 0.15) !important;
  border-color: rgba(37, 99, 235, 0.3) !important;
  color: var(--text-primary, #1e293b) !important;
}

:deep(.el-pagination .el-pagination__jump) {
  color: var(--text-secondary, #475569);
  font-family: 'DM Sans', sans-serif;
}

:deep(.el-pagination .el-pagination__total) {
  color: var(--text-secondary, #475569);
  font-family: 'DM Sans', sans-serif;
}

/* ============================================
   Element Plus Empty 覆盖
   ============================================ */

:deep(.el-empty__description) {
  color: var(--text-secondary, #475569) !important;
  font-family: 'DM Sans', sans-serif;
}

/* Element Plus Button 主要按钮 */
:deep(.el-button--primary) {
  --el-button-bg-color: #2563eb;
  --el-button-border-color: #2563eb;
  --el-button-hover-bg-color: #3b82f6;
  --el-button-hover-border-color: #3b82f6;
  --el-button-active-bg-color: #0891b2;
  --el-button-active-border-color: #0891b2;
  background: linear-gradient(135deg, #2563eb, #0891b2);
  border: none;
  font-family: 'DM Sans', sans-serif;
  border-radius: 10px;
}

:deep(.el-button--primary:hover) {
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.3);
  transform: translateY(-1px);
}

/* ============================================
   响应式布局
   ============================================ */

@media (max-width: 1400px) {
  .book-grid,
  .skeleton-grid {
    grid-template-columns: repeat(3, minmax(200px, 1fr));
  }
}

@media (max-width: 1200px) {
  .sidebar {
    width: 220px;
  }

  .book-grid,
  .skeleton-grid {
    grid-template-columns: repeat(3, minmax(180px, 1fr));
  }
}

@media (max-width: 992px) {
  .content-area {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    min-height: auto;
    border-right: none;
    border-bottom: 1px solid var(--border-color, #e2e8f0);
    border-radius: 0;
  }

  .sidebar.collapsed {
    width: 100%;
    height: auto;
  }

  .sidebar-content {
    max-height: none;
  }

  .main-content {
    padding: 24px 20px;
  }

  .book-grid,
  .skeleton-grid {
    grid-template-columns: repeat(2, minmax(160px, 1fr));
  }
}

@media (max-width: 768px) {
  .header {
    flex-direction: column;
    gap: 20px;
    align-items: flex-start;
    padding: 24px 20px;
  }

  .header h1 {
    font-size: 24px;
  }

  .search-area {
    width: 100%;
    flex-direction: column;
  }

  .search-input {
    width: 100%;
  }

  .hot-search-section {
    flex-direction: column;
    gap: 24px;
  }

  .filter-info {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }
}

@media (max-width: 480px) {
  .header {
    padding: 20px 16px;
  }

  .header h1 {
    font-size: 20px;
  }

  .book-grid,
  .skeleton-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
}
</style>
