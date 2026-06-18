<template>
  <div class="compare-charts">
    <div ref="chartRef1" class="chart-container"></div>
    <div ref="chartRef2" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: { type: Object, default: () => ({}) }
})

const chartRef1 = ref(null)
const chartRef2 = ref(null)
let chart1 = null
let chart2 = null

const ORANGE = '#F97316'
const ORANGE_LIGHT = '#fb923c'
const BLUE = '#3b82f6'
const GREEN = '#10b981'
const GRID_LINE = '#e2e8f0'
const TEXT_COLOR = '#475569'

const initCharts = () => {
  if (chartRef1.value) chart1 = echarts.init(chartRef1.value)
  if (chartRef2.value) chart2 = echarts.init(chartRef2.value)
  updateCharts()
}

const fmt = (v) => {
  if (v === undefined || v === null || Number.isNaN(Number(v))) return 0
  return Number(v) || 0
}

const updateCharts = () => {
  const compare = props.data.comparison || props.data
  const rmse = compare.rmse || {}
  const mae = compare.mae || {}

  // 处理 cf 预测失败的情况 - 用 N/A 展示
  const cfRmse = rmse.cf === null || rmse.cf === undefined ? null : Number(rmse.cf)
  const svdRmse = rmse.svd === null || rmse.svd === undefined ? null : Number(rmse.svd)
  const cfMae = mae.cf === null || mae.cf === undefined ? null : Number(mae.cf)
  const svdMae = mae.svd === null || mae.svd === undefined ? null : Number(mae.svd)

  const errorOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#ffffff',
      borderColor: '#e2e8f0',
      textStyle: { color: '#1e293b' }
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

  // Precision/Recall line chart
  const metrics = props.data.ranking_metrics || {}
  const ks = [5, 10, 20]

  const precSeries = (prefix, color, label) => ({
    name: label,
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 10,
    data: ks.map((k) => {
      const v = metrics[`${prefix}_precision@${k}`]
      return v === undefined || v === null ? null : Number(v) * 100
    }),
    lineStyle: { color, width: 3 },
    itemStyle: { color, borderWidth: 2 },
    areaStyle: {
      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: color + '55' }, { offset: 1, color: color + '00' }
      ])
    }
  })

  const rankingOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#e2e8f0',
      textStyle: { color: '#1e293b' },
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
      data: ['CF Precision', 'SVD Precision'],
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
      name: 'Precision (%)',
      min: 0,
      axisLabel: { color: TEXT_COLOR, formatter: (v) => v.toFixed(0) + '%' },
      axisLine: { lineStyle: { color: GRID_LINE } },
      splitLine: { lineStyle: { color: GRID_LINE, type: 'dashed' } }
    },
    series: [
      precSeries('cf', ORANGE, 'CF Precision'),
      precSeries('svd', BLUE, 'SVD Precision')
    ]
  }

  if (chart1) chart1.setOption(errorOption)
  if (chart2) chart2.setOption(rankingOption)
}

const handleResize = () => {
  chart1?.resize()
  chart2?.resize()
}

watch(() => props.data, updateCharts, { deep: true })

onMounted(() => {
  initCharts()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  chart1?.dispose()
  chart2?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.compare-charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.chart-container {
  width: 100%;
  height: 380px;
}

@media (max-width: 900px) {
  .compare-charts {
    grid-template-columns: 1fr;
  }
  .chart-container {
    height: 320px;
  }
}
</style>
