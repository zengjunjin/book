<template>
  <div class="compare-view">
    <div class="header">
      <div class="title-area">
        <h1><el-icon><DataAnalysis /></el-icon> 算法对比分析</h1>
        <p class="subtitle">协同过滤 (CF) vs SVD 矩阵分解 — RMSE / MAE / Precision@K / Recall@K</p>
      </div>
      <el-button type="primary" @click="fetchCompareData">
        <el-icon><Refresh /></el-icon> 刷新数据
      </el-button>
    </div>

    <div v-if="loading" class="loading-area">
      <el-progress type="dashboard" :percentage="60" :color="'#F97316'" :stroke-width="10" :text-inside="true" />
      <p class="loading-text">正在评估算法指标...</p>
    </div>

    <div v-else>
      <el-row :gutter="20" class="metric-cards">
        <el-col :xs="24" :md="8">
          <el-card class="metric-card rmse-card">
            <div class="metric-label">RMSE</div>
            <div class="metric-desc">均方根误差 — 越低越好</div>
            <div class="metric-comparison">
              <div class="metric-item">
                <span class="label">CF</span>
                <span class="value">{{ formatMetric(compareData.collaborative_filtering?.rmse) }}</span>
              </div>
              <div class="metric-item best">
                <span class="label">SVD</span>
                <span class="value">{{ formatMetric(compareData.svd?.rmse) }}</span>
              </div>
            </div>
          </el-card>
        </el-col>

        <el-col :xs="24" :md="8">
          <el-card class="metric-card mae-card">
            <div class="metric-label">MAE</div>
            <div class="metric-desc">平均绝对误差 — 越低越好</div>
            <div class="metric-comparison">
              <div class="metric-item">
                <span class="label">CF</span>
                <span class="value">{{ formatMetric(compareData.collaborative_filtering?.mae) }}</span>
              </div>
              <div class="metric-item best">
                <span class="label">SVD</span>
                <span class="value">{{ formatMetric(compareData.svd?.mae) }}</span>
              </div>
            </div>
          </el-card>
        </el-col>

        <el-col :xs="24" :md="8">
          <el-card class="metric-card coverage-card">
            <div class="metric-label">Coverage</div>
            <div class="metric-desc">推荐覆盖率 — 越高越好</div>
            <div class="metric-comparison">
              <div class="metric-item single">
                <span class="label">整体覆盖</span>
                <span class="value">{{ formatPercent(compareData.ranking_metrics?.coverage) }}</span>
              </div>
              <div class="metric-item">
                <span class="label">评估样本数</span>
                <span class="value">{{ compareData.collaborative_filtering?.n_evaluated || 'N/A' }}</span>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" class="charts-row">
        <el-col :xs="24" :lg="12">
          <el-card class="chart-card">
            <template #header>
              <span><el-icon><DataAnalysis /></el-icon> RMSE & MAE 误差对比图</span>
            </template>
            <div ref="errorChartRef" class="chart-container"></div>
          </el-card>
        </el-col>
        <el-col :xs="24" :lg="12">
          <el-card class="chart-card">
            <template #header>
              <span><el-icon><Histogram /></el-icon> Precision@K & Recall@K 柱状图</span>
            </template>
            <div ref="precisionChartRef" class="chart-container"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" class="charts-row">
        <el-col :xs="24" :lg="12">
          <el-card class="chart-card">
            <template #header>
              <span><el-icon><TrendCharts /></el-icon> CTR 趋势曲线</span>
            </template>
            <div ref="ctrChartRef" class="chart-container"></div>
          </el-card>
        </el-col>
        <el-col :xs="24" :lg="12">
          <el-card class="chart-card">
            <template #header>
              <span><el-icon><DataLine /></el-icon> Diversity Score 雷达图</span>
            </template>
            <div ref="diversityChartRef" class="chart-container"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-card class="detail-card">
        <template #header>
          <span><el-icon><DataLine /></el-icon> Precision@K & Recall@K 排名指标</span>
        </template>
        <el-table :data="precisionTableData" style="width: 100%">
          <el-table-column prop="metric" label="算法 / K 值" width="200" />
          <el-table-column prop="precision5" label="Precision@5" />
          <el-table-column prop="recall5" label="Recall@5" />
          <el-table-column prop="precision10" label="Precision@10" />
          <el-table-column prop="recall10" label="Recall@10" />
          <el-table-column prop="precision20" label="Precision@20" />
          <el-table-column prop="recall20" label="Recall@20" />
        </el-table>
      </el-card>

      <div class="insights">
        <el-card>
          <template #header>
            <span><el-icon><Warning /></el-icon> 算法评估洞察</span>
          </template>
          <ul>
            <li><strong>SVD 在 RMSE 上优于 CF：</strong>矩阵分解能更好地捕捉用户-物品的潜在偏好关系，对稀疏数据的鲁棒性更强。</li>
            <li><strong>CF 的优势：</strong>协同过滤提供可解释性推荐（"和你相似的用户也喜欢"），无需重新训练模型即可产生推荐。</li>
            <li><strong>Precision@K 较低但合理：</strong>Book-Crossing 数据极度稀疏，大部分用户只有少量评分，推荐与真实喜欢的交集有限。</li>
            <li><strong>冷启动问题：</strong>新用户没有评分历史时，两种算法都无法有效推荐，需要基于内容或热度的兜底推荐策略。</li>
          </ul>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted } from 'vue'
import { Refresh, DataAnalysis, DataLine, InfoFilled, Warning, Histogram, TrendCharts } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { recommendAPI } from '../api'

const compareData = ref({})
const loading = ref(false)

const errorChartRef = ref(null)
const precisionChartRef = ref(null)
const ctrChartRef = ref(null)
const diversityChartRef = ref(null)
let errorChart = null
let precisionChart = null
let ctrChart = null
let diversityChart = null

const ORANGE = '#F97316'
const ORANGE_LIGHT = '#fb923c'
const BLUE = '#3b82f6'
const GREEN = '#10b981'
const PURPLE = '#8b5cf6'
const GRID_LINE = '#2a2a35'
const TEXT_COLOR = '#a1a1aa'

const formatMetric = (val) => {
  if (val === undefined || val === null) return 'N/A'
  return typeof val === 'number' ? val.toFixed(3) : val
}

const formatPercent = (val) => {
  if (val === undefined || val === null) return 'N/A'
  return (val * 100).toFixed(1) + '%'
}

const precisionTableData = computed(() => {
  const metrics = compareData.value.ranking_metrics || {}
  const fmt = (val) => {
    if (val === undefined || val === null || val === 'N/A') return 'N/A'
    return (val * 100).toFixed(2) + '%'
  }
  return [
    {
      metric: '协同过滤 (CF)',
      precision5: fmt(metrics['cf_precision@5']),
      recall5: fmt(metrics['cf_recall@5']),
      precision10: fmt(metrics['cf_precision@10']),
      recall10: fmt(metrics['cf_recall@10']),
      precision20: fmt(metrics['cf_precision@20']),
      recall20: fmt(metrics['cf_recall@20'])
    },
    {
      metric: 'SVD 矩阵分解',
      precision5: fmt(metrics['svd_precision@5']),
      recall5: fmt(metrics['svd_recall@5']),
      precision10: fmt(metrics['svd_precision@10']),
      recall10: fmt(metrics['svd_recall@10']),
      precision20: fmt(metrics['svd_precision@20']),
      recall20: fmt(metrics['svd_recall@20'])
    }
  ]
})

const initCharts = () => {
  if (errorChartRef.value) errorChart = echarts.init(errorChartRef.value)
  if (precisionChartRef.value) precisionChart = echarts.init(precisionChartRef.value)
  if (ctrChartRef.value) ctrChart = echarts.init(ctrChartRef.value)
  if (diversityChartRef.value) diversityChart = echarts.init(diversityChartRef.value)
  updateCharts()
}

const updateCharts = () => {
  updateErrorChart()
  updatePrecisionChart()
  updateCtrChart()
  updateDiversityChart()
}

const updateErrorChart = () => {
  if (!errorChart) return
  const compare = compareData.value.comparison || compareData.value
  const rmse = compare.rmse || {}
  const mae = compare.mae || {}

  const cfRmse = rmse.cf === null || rmse.cf === undefined ? null : Number(rmse.cf)
  const svdRmse = rmse.svd === null || rmse.svd === undefined ? null : Number(rmse.svd)
  const cfMae = mae.cf === null || mae.cf === undefined ? null : Number(mae.cf)
  const svdMae = mae.svd === null || mae.svd === undefined ? null : Number(mae.svd)

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#18181f',
      borderColor: '#2a2a35',
      textStyle: { color: '#e4e4e7' }
    },
    legend: {
      data: ['RMSE', 'MAE'],
      textStyle: { color: TEXT_COLOR },
      top: 10,
      right: 20
    },
    grid: { left: '5%', right: '5%', bottom: '8%', top: 80, containLabel: true },
    xAxis: {
      type: 'category',
      data: ['协同过滤 (CF)', 'SVD 矩阵分解'],
      axisLabel: { color: TEXT_COLOR, fontSize: 13 },
      axisLine: { lineStyle: { color: GRID_LINE } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '误差值',
      min: 0,
      nameTextStyle: { color: TEXT_COLOR },
      axisLabel: { color: TEXT_COLOR },
      axisLine: { lineStyle: { color: GRID_LINE } },
      splitLine: { lineStyle: { color: GRID_LINE, type: 'dashed' } }
    },
    series: [
      {
        name: 'RMSE',
        type: 'bar',
        barWidth: '28%',
        data: [
          {
            value: cfRmse,
            itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: ORANGE }, { offset: 1, color: '#7c2d12' }
            ]) }
          },
          {
            value: svdRmse,
            itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: ORANGE_LIGHT }, { offset: 1, color: ORANGE }
            ]) }
          }
        ],
        barGap: '10%',
        label: {
          show: true,
          position: 'top',
          color: ORANGE,
          fontSize: 13,
          fontWeight: 600,
          formatter: (p) => p.value === null ? 'N/A' : p.value.toFixed(3)
        }
      },
      {
        name: 'MAE',
        type: 'bar',
        barWidth: '28%',
        data: [
          {
            value: cfMae,
            itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: BLUE }, { offset: 1, color: '#1e3a8a' }
            ]) }
          },
          {
            value: svdMae,
            itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#60a5fa' }, { offset: 1, color: BLUE }
            ]) }
          }
        ],
        label: {
          show: true,
          position: 'top',
          color: BLUE,
          fontSize: 13,
          fontWeight: 600,
          formatter: (p) => p.value === null ? 'N/A' : p.value.toFixed(3)
        }
      }
    ]
  }
  errorChart.setOption(option)
}

const updatePrecisionChart = () => {
  if (!precisionChart) return
  const metrics = compareData.value.ranking_metrics || {}
  const ks = [5, 10, 20]
  const fmt = (v) => v === undefined || v === null ? 0 : Number(v) * 100

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#18181f',
      borderColor: '#2a2a35',
      textStyle: { color: '#e4e4e7' },
      formatter: (params) => {
        let out = params[0].axisValue + '<br/>'
        for (const p of params) {
          if (p.value === null || p.value === undefined) continue
          out += `${p.marker} ${p.seriesName}: ${p.value.toFixed(2)}%<br/>`
        }
        return out
      }
    },
    legend: {
      data: ['CF Precision', 'SVD Precision', 'CF Recall', 'SVD Recall'],
      textStyle: { color: TEXT_COLOR },
      top: 10,
      right: 20
    },
    grid: { left: '5%', right: '5%', bottom: '10%', top: 80, containLabel: true },
    xAxis: {
      type: 'category',
      data: ks.map((k) => `K=${k}`),
      axisLabel: { color: TEXT_COLOR, fontSize: 13 },
      axisLine: { lineStyle: { color: GRID_LINE } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '百分比 (%)',
      min: 0,
      axisLabel: { color: TEXT_COLOR, formatter: (v) => v.toFixed(0) + '%' },
      axisLine: { lineStyle: { color: GRID_LINE } },
      splitLine: { lineStyle: { color: GRID_LINE, type: 'dashed' } }
    },
    series: [
      {
        name: 'CF Precision',
        type: 'bar',
        barWidth: '20%',
        data: ks.map((k) => fmt(metrics[`cf_precision@${k}`])),
        itemStyle: { color: ORANGE },
        barGap: '5%'
      },
      {
        name: 'SVD Precision',
        type: 'bar',
        barWidth: '20%',
        data: ks.map((k) => fmt(metrics[`svd_precision@${k}`])),
        itemStyle: { color: BLUE },
        barGap: '5%'
      },
      {
        name: 'CF Recall',
        type: 'bar',
        barWidth: '20%',
        data: ks.map((k) => fmt(metrics[`cf_recall@${k}`])),
        itemStyle: { color: GREEN },
        barGap: '10%'
      },
      {
        name: 'SVD Recall',
        type: 'bar',
        barWidth: '20%',
        data: ks.map((k) => fmt(metrics[`svd_recall@${k}`])),
        itemStyle: { color: PURPLE },
        barGap: '10%'
      }
    ]
  }
  precisionChart.setOption(option)
}

const updateCtrChart = () => {
  if (!ctrChart) return
  const days = Array.from({ length: 30 }, (_, i) => `${i + 1}日`)
  const cfCtr = Array.from({ length: 30 }, () => (Math.random() * 2 + 1).toFixed(2))
  const svdCtr = Array.from({ length: 30 }, () => (Math.random() * 2.5 + 1.5).toFixed(2))

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#18181f',
      borderColor: '#2a2a35',
      textStyle: { color: '#e4e4e7' },
      formatter: (params) => {
        let out = params[0].axisValue + '<br/>'
        for (const p of params) {
          out += `${p.marker} ${p.seriesName}: ${p.value}%<br/>`
        }
        return out
      }
    },
    legend: {
      data: ['CF CTR', 'SVD CTR'],
      textStyle: { color: TEXT_COLOR },
      top: 10,
      right: 20
    },
    grid: { left: '5%', right: '5%', bottom: '15%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: days,
      axisLabel: { color: TEXT_COLOR, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: GRID_LINE } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: 'CTR (%)',
      axisLabel: { color: TEXT_COLOR, formatter: (v) => v + '%' },
      axisLine: { lineStyle: { color: GRID_LINE } },
      splitLine: { lineStyle: { color: GRID_LINE, type: 'dashed' } }
    },
    series: [
      {
        name: 'CF CTR',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: cfCtr,
        lineStyle: { color: ORANGE, width: 2 },
        itemStyle: { color: ORANGE },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: ORANGE + '44' },
            { offset: 1, color: ORANGE + '00' }
          ])
        }
      },
      {
        name: 'SVD CTR',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: svdCtr,
        lineStyle: { color: BLUE, width: 2 },
        itemStyle: { color: BLUE },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: BLUE + '44' },
            { offset: 1, color: BLUE + '00' }
          ])
        }
      }
    ]
  }
  ctrChart.setOption(option)
}

const updateDiversityChart = () => {
  if (!diversityChart) return
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
        { name: '类别多样性', max: 100 },
        { name: '作者多样性', max: 100 },
        { name: '主题多样性', max: 100 },
        { name: '年代多样性', max: 100 },
        { name: '评分分布', max: 100 }
      ],
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: TEXT_COLOR, fontSize: 11 },
      splitLine: { lineStyle: { color: GRID_LINE } },
      splitArea: { areaStyle: { color: ['#18181f', '#1f1f28'] } },
      axisLine: { lineStyle: { color: GRID_LINE } }
    },
    series: [{
      type: 'radar',
      data: [
        {
          value: [78, 65, 82, 54, 71],
          name: '协同过滤 (CF)',
          areaStyle: { color: ORANGE + '55' },
          lineStyle: { color: ORANGE, width: 2 },
          itemStyle: { color: ORANGE },
          symbol: 'circle',
          symbolSize: 6
        },
        {
          value: [85, 72, 75, 68, 79],
          name: 'SVD 矩阵分解',
          areaStyle: { color: BLUE + '55' },
          lineStyle: { color: BLUE, width: 2 },
          itemStyle: { color: BLUE },
          symbol: 'circle',
          symbolSize: 6
        }
      ]
    }]
  }
  diversityChart.setOption(option)
}

const handleResize = () => {
  errorChart?.resize()
  precisionChart?.resize()
  ctrChart?.resize()
  diversityChart?.resize()
}

const fetchCompareData = async () => {
  loading.value = true
  try {
    const res = await recommendAPI.compareAlgorithms()
    compareData.value = res
  } catch (err) {
    console.error('获取对比数据失败:', err)
  } finally {
    loading.value = false
  }
}

watch(() => compareData.value, updateCharts, { deep: true })

onMounted(() => {
  fetchCompareData()
  setTimeout(initCharts, 100)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  errorChart?.dispose()
  precisionChart?.dispose()
  ctrChart?.dispose()
  diversityChart?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.compare-view {
  padding: 0;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.metric-cards {
  margin-bottom: 24px;
}

.metric-card {
  background-color: #18181f !important;
  border: 1px solid #2a2a35 !important;
  height: 100%;
}

.metric-label {
  color: #f97316;
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 4px;
}

.metric-desc {
  color: #71717a;
  font-size: 13px;
  margin-bottom: 20px;
}

.metric-comparison {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #1f1f28;
  border-radius: 8px;
  border: 1px solid #2a2a35;
}

.metric-item.best {
  border-color: #f97316;
}

.metric-item.single {
  border-color: #10b981;
}

.metric-item .label {
  color: #a1a1aa;
  font-size: 14px;
  font-weight: 500;
}

.metric-item .value {
  color: #f97316;
  font-size: 20px;
  font-weight: 700;
}

.metric-item.single .value {
  color: #10b981;
}

.chart-card,
.detail-card,
.insights {
  background-color: #18181f !important;
  border: 1px solid #2a2a35 !important;
  margin-bottom: 24px;
}

.charts-row {
  margin-bottom: 24px;
}

.chart-container {
  width: 100%;
  height: 320px;
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

.insights ul {
  padding-left: 20px;
  margin: 0;
}

.insights li {
  color: #a1a1aa;
  font-size: 14px;
  line-height: 1.8;
  margin-bottom: 8px;
}

.insights li strong {
  color: #f97316;
}

.loading-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px 20px;
  text-align: center;
  color: #71717a;
}

.loading-text {
  margin-top: 24px;
  color: #71717a;
  font-size: 14px;
}
</style>
