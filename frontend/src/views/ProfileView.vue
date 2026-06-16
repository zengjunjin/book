<template>
  <div class="profile-view">
    <div class="header">
      <div class="title-area">
        <h1><el-icon><UserFilled /></el-icon> 个人中心</h1>
        <p class="subtitle">管理您的评分历史与账户设置</p>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :xs="24" :md="8">
        <el-card class="user-info">
          <template #header>
            <span><el-icon><UserFilled /></el-icon> 用户信息</span>
          </template>
          <div class="profile-pic">
            <el-avatar :size="80" style="background-color: #F97316; font-size: 32px; font-weight: 700">
              {{ firstLetter }}
            </el-avatar>
          </div>
          <div class="info-row">
            <span class="info-label">用户名</span>
            <span class="info-value">{{ userStore.user?.username || 'N/A' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">邮箱</span>
            <span class="info-value">{{ userStore.user?.email || '未设置' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">用户 ID</span>
            <span class="info-value">{{ userStore.user?.id || 'N/A' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">评分历史</span>
            <span class="info-value">{{ totalRatings }} 条</span>
          </div>
          <div style="margin-top: 20px">
            <el-button type="danger" @click="handleLogout" style="width: 100%">
              <el-icon><SwitchButton /></el-icon> 退出登录
            </el-button>
          </div>
        </el-card>

        <el-card class="reading-dashboard">
          <template #header>
            <span><el-icon><Timer /></el-icon> 阅读时长统计</span>
          </template>
          <div ref="dashboardRef" class="dashboard-chart"></div>
          <div class="dashboard-stats">
            <div class="stat-item">
              <span class="stat-label">总阅读时长</span>
              <span class="stat-value">{{ readingStats.totalHours }} 小时</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">日均阅读</span>
              <span class="stat-value">{{ readingStats.dailyAvg }} 分钟</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="16">
        <el-card class="rating-history">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span><el-icon><Reading /></el-icon> 我的评分历史</span>
              <span style="color: #909399; font-size: 13px">共 {{ totalRatings }} 条评分</span>
            </div>
          </template>

          <div v-if="loading" class="loading-area">
            <el-skeleton v-for="i in 5" :key="i" :rows="1" animated />
          </div>

          <div v-else-if="ratings.length === 0" class="empty-area">
            <el-empty description="暂无评分记录 — 去首页给书籍打分吧！">
              <el-button type="primary" @click="$router.push('/')">去打分</el-button>
            </el-empty>
          </div>

          <el-table v-else :data="ratings" style="width: 100%">
            <el-table-column label="书籍" min-width="300">
              <template #default="scope">
                <div class="book-cell">
                  <img
                    v-if="scope.row.book?.image_url"
                    :src="scope.row.book.image_url"
                    class="book-thumb"
                  />
                  <div class="book-cell-info">
                    <div class="book-cell-title">{{ scope.row.book?.title || 'N/A' }}</div>
                    <div class="book-cell-author">{{ scope.row.book?.author || '未知' }}</div>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="我的评分" width="180">
              <template #default="scope">
                <el-rate :model-value="scope.row.rating" disabled show-score :max="10" />
              </template>
            </el-table-column>
            <el-table-column label="评分时间" width="180">
              <template #default="scope">
                <span>{{ formatDate(scope.row.created_at) }}</span>
              </template>
            </el-table-column>
          </el-table>

          <div v-if="totalPages > 1" class="pagination">
            <el-pagination
              v-model:current-page="currentPage"
              :page-size="20"
              :total="totalRatings"
              layout="prev, pager, next"
              background
              @current-change="handlePageChange"
            />
          </div>
        </el-card>

        <el-row :gutter="20" class="charts-row">
          <el-col :xs="24" :lg="12">
            <el-card class="chart-card">
              <template #header>
                <span><el-icon><DataLine /></el-icon> 阅读偏好雷达图</span>
              </template>
              <div ref="radarChartRef" class="chart-container"></div>
            </el-card>
          </el-col>
          <el-col :xs="24" :lg="12">
            <el-card class="chart-card">
              <template #header>
                <span><el-icon><PieChart /></el-icon> 书籍类别分布</span>
              </template>
              <div ref="pieChartRef" class="chart-container"></div>
            </el-card>
          </el-col>
        </el-row>

        <el-card class="chart-card trend-card">
          <template #header>
            <span><el-icon><TrendCharts /></el-icon> 阅读趋势（每月阅读量）</span>
          </template>
          <div ref="trendChartRef" class="trend-chart-container"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UserFilled, SwitchButton, Reading, Timer, DataLine, PieChart, TrendCharts } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { ratingAPI } from '../api'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()

const ratings = ref([])
const loading = ref(false)
const currentPage = ref(1)
const totalRatings = ref(0)
const totalPages = ref(0)

const radarChartRef = ref(null)
const pieChartRef = ref(null)
const trendChartRef = ref(null)
const dashboardRef = ref(null)
let radarChart = null
let pieChart = null
let trendChart = null
let dashboardChart = null

const ORANGE = '#F97316'
const ORANGE_LIGHT = '#fb923c'
const BLUE = '#3b82f6'
const GREEN = '#10b981'
const PURPLE = '#8b5cf6'
const GRID_LINE = '#2a2a35'
const TEXT_COLOR = '#a1a1aa'

const firstLetter = computed(() => {
  const name = userStore.user?.username || 'U'
  return name.charAt(0).toUpperCase()
})

const readingStats = computed(() => {
  const total = totalRatings.value * 45
  const hours = Math.floor(total / 60)
  const dailyAvg = totalRatings.value > 0 ? Math.round(total / 30) : 0
  return { totalHours: hours, dailyAvg }
})

const fetchRatings = async () => {
  if (!userStore.isLoggedIn) return
  loading.value = true
  try {
    const res = await ratingAPI.getUserRatings(userStore.user.id, currentPage.value, 20)
    ratings.value = res.ratings || []
    totalRatings.value = res.total || ratings.value.length
    totalPages.value = res.pages || Math.ceil(totalRatings.value / 20) || 1
  } catch (err) {
    console.error('获取评分历史失败:', err)
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page) => {
  currentPage.value = page
  fetchRatings()
}

const handleLogout = () => {
  userStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

const formatDate = (dateStr) => {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN') + ' ' +
         date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const initCharts = () => {
  if (radarChartRef.value) radarChart = echarts.init(radarChartRef.value)
  if (pieChartRef.value) pieChart = echarts.init(pieChartRef.value)
  if (trendChartRef.value) trendChart = echarts.init(trendChartRef.value)
  if (dashboardRef.value) dashboardChart = echarts.init(dashboardRef.value)
  updateCharts()
}

const updateCharts = () => {
  updateRadarChart()
  updatePieChart()
  updateTrendChart()
  updateDashboardChart()
}

const updateRadarChart = () => {
  if (!radarChart) return
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#18181f',
      borderColor: '#2a2a35',
      textStyle: { color: '#e4e4e7' }
    },
    legend: {
      bottom: 10,
      textStyle: { color: TEXT_COLOR }
    },
    radar: {
      indicator: [
        { name: '小说', max: 100 },
        { name: '科幻', max: 100 },
        { name: '历史', max: 100 },
        { name: '技术', max: 100 },
        { name: '传记', max: 100 },
        { name: '悬疑', max: 100 }
      ],
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: TEXT_COLOR, fontSize: 12 },
      splitLine: { lineStyle: { color: GRID_LINE } },
      splitArea: { areaStyle: { color: ['#18181f', '#1f1f28'] } },
      axisLine: { lineStyle: { color: GRID_LINE } }
    },
    series: [{
      type: 'radar',
      data: [{
        value: [75, 60, 45, 80, 35, 55],
        name: '阅读偏好',
        areaStyle: { color: ORANGE + '55' },
        lineStyle: { color: ORANGE, width: 2 },
        itemStyle: { color: ORANGE },
        symbol: 'circle',
        symbolSize: 6
      }]
    }]
  }
  radarChart.setOption(option)
}

const updatePieChart = () => {
  if (!pieChart) return
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#18181f',
      borderColor: '#2a2a35',
      textStyle: { color: '#e4e4e7' },
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: TEXT_COLOR }
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 6,
        borderColor: '#18181f',
        borderWidth: 2
      },
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold', color: '#e4e4e7' }
      },
      data: [
        { value: 35, name: '小说', itemStyle: { color: ORANGE } },
        { value: 20, name: '科幻', itemStyle: { color: BLUE } },
        { value: 15, name: '历史', itemStyle: { color: GREEN } },
        { value: 12, name: '技术', itemStyle: { color: PURPLE } },
        { value: 10, name: '传记', itemStyle: { color: '#ec4899' },
          value: 8, name: '悬疑', itemStyle: { color: '#f59e0b' }
        }
      ]
    }]
  }
  pieChart.setOption(option)
}

const updateTrendChart = () => {
  if (!trendChart) return
  const months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
  const data = [12, 8, 15, 10, 18, 22, 16, 20, 14, 19, 25, 28]
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#18181f',
      borderColor: '#2a2a35',
      textStyle: { color: '#e4e4e7' },
      formatter: '{b}: {c} 本书'
    },
    grid: { left: '3%', right: '5%', bottom: '10%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { color: TEXT_COLOR, fontSize: 11 },
      axisLine: { lineStyle: { color: GRID_LINE } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '阅读量',
      nameTextStyle: { color: TEXT_COLOR },
      axisLabel: { color: TEXT_COLOR },
      axisLine: { lineStyle: { color: GRID_LINE } },
      splitLine: { lineStyle: { color: GRID_LINE, type: 'dashed' } }
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      data,
      lineStyle: { color: ORANGE, width: 3 },
      itemStyle: { color: ORANGE, borderWidth: 2, borderColor: '#fff' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: ORANGE + '66' },
          { offset: 1, color: ORANGE + '00' }
        ])
      }
    }]
  }
  trendChart.setOption(option)
}

const updateDashboardChart = () => {
  if (!dashboardChart) return
  const option = {
    backgroundColor: 'transparent',
    series: [{
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max: 100,
      splitNumber: 5,
      radius: '90%',
      center: ['50%', '60%'],
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: ORANGE },
          { offset: 1, color: ORANGE_LIGHT }
        ])
      },
      progress: {
        show: true,
        width: 12,
        roundCap: true
      },
      pointer: { show: false },
      axisLine: {
        lineStyle: { width: 12, color: [[1, '#2a2a35']] }
      },
      axisTick: { show: false },
      splitLine: {
        length: 8,
        lineStyle: { width: 2, color: GRID_LINE }
      },
      axisLabel: { show: false },
      anchor: { show: false },
      title: {
        offsetCenter: [0, '20%'],
        fontSize: 12,
        color: TEXT_COLOR
      },
      detail: {
        valueAnimation: true,
        offsetCenter: [0, '-10%'],
        fontSize: 28,
        fontWeight: 'bold',
        formatter: '{value}%',
        color: ORANGE
      },
      data: [{
        value: Math.round(totalRatings.value / 2),
        name: '目标完成'
      }]
    }]
  }
  dashboardChart.setOption(option)
}

const handleResize = () => {
  radarChart?.resize()
  pieChart?.resize()
  trendChart?.resize()
  dashboardChart?.resize()
}

watch(() => ratings.value, updateCharts, { deep: true })

onMounted(() => {
  fetchRatings()
  setTimeout(initCharts, 100)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  radarChart?.dispose()
  pieChart?.dispose()
  trendChart?.dispose()
  dashboardChart?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.profile-view {
  padding: 0;
}

.header {
  margin-bottom: 32px;
  padding: 0 0 24px 0;
  border-bottom: 1px solid #2a2a35;
}

.title-area h1 {
  color: #e4e4e7;
  margin: 0 0 6px 0;
  font-size: 28px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 12px;
}

.subtitle {
  color: #71717a;
  margin: 0;
  font-size: 14px;
}

.user-info,
.rating-history,
.reading-dashboard {
  height: 100%;
  background-color: #18181f !important;
  border: 1px solid #2a2a35 !important;
}

.reading-dashboard {
  margin-top: 20px;
}

.dashboard-chart {
  width: 100%;
  height: 200px;
}

.dashboard-stats {
  display: flex;
  justify-content: space-around;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #2a2a35;
}

.stat-item {
  text-align: center;
}

.stat-label {
  display: block;
  color: #71717a;
  font-size: 12px;
  margin-bottom: 4px;
}

.stat-value {
  color: #f97316;
  font-size: 18px;
  font-weight: 700;
}

.charts-row {
  margin-top: 24px;
}

.chart-card {
  background-color: #18181f !important;
  border: 1px solid #2a2a35 !important;
  margin-bottom: 24px;
}

.trend-card {
  margin-top: 0;
}

.chart-container {
  width: 100%;
  height: 280px;
}

.trend-chart-container {
  width: 100%;
  height: 300px;
}

:deep(.el-card__header) {
  background-color: transparent !important;
  border-bottom: 1px solid #2a2a35 !important;
  font-size: 16px;
  font-weight: 600;
  color: #e4e4e7;
  padding: 18px 24px;
}

:deep(.el-card__header span) {
  display: flex;
  align-items: center;
  gap: 8px;
}

:deep(.el-card__header .el-icon) {
  color: #f97316;
}

:deep(.el-card__body) {
  background-color: transparent !important;
  padding: 24px;
}

.profile-pic {
  display: flex;
  justify-content: center;
  margin-bottom: 24px;
  padding: 20px 0;
}

:deep(.el-avatar) {
  background-color: #f97316 !important;
  font-size: 32px;
  font-weight: 700;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #2a2a35;
  font-size: 14px;
}

.info-row:last-of-type {
  border-bottom: none;
}

.info-label {
  color: #71717a;
}

.info-value {
  color: #e4e4e7;
  font-weight: 500;
}

:deep(.el-table) {
  background-color: transparent !important;
}

:deep(.el-table tr) {
  background-color: transparent !important;
}

:deep(.el-table th.el-table__cell) {
  background-color: #1f1f28 !important;
  color: #e4e4e7;
  border-bottom: 1px solid #2a2a35;
}

:deep(.el-table td.el-table__cell) {
  border-bottom: 1px solid #2a2a35;
  color: #a1a1aa;
}

:deep(.el-table--enable-row-hover .el-table__body tr:hover > td.el-table__cell) {
  background-color: #1f1f28 !important;
}

.book-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.book-thumb {
  width: 40px;
  height: 56px;
  object-fit: cover;
  border-radius: 4px;
  background-color: #1f1f28;
}

.book-cell-info {
  flex: 1;
  min-width: 0;
}

.book-cell-title {
  color: #e4e4e7;
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.book-cell-author {
  color: #71717a;
  font-size: 12px;
}

.pagination {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}

.loading-area,
.empty-area {
  padding: 20px 0;
  text-align: center;
  color: #71717a;
}
</style>
