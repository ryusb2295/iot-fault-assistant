<script setup>
import { ref, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])
const props = defineProps({ points: { type: Array, default: () => [] } })
const chartEl = ref(null)
let chart
let observer
const render = () => {
  if (!chart || !props.points.length) return
  chart.setOption({
    color: ['#3476dc', '#e49b28', '#dc5d5d'],
    tooltip: { trigger: 'axis' }, legend: { bottom: 0, icon: 'circle', itemWidth: 9, textStyle: { color: '#64748b' } },
    grid: { top: 18, right: 20, bottom: 50, left: 38 },
    xAxis: { type: 'category', boundaryGap: false, data: props.points.map((p) => p.label), axisLine: { lineStyle: { color: '#dfe5ee' } }, axisLabel: { color: '#8994a7' } },
    yAxis: { type: 'value', min: 0, splitLine: { lineStyle: { color: '#edf0f5' } }, axisLabel: { color: '#8994a7' } },
    series: [
      { name: '정상 메시지', type: 'line', smooth: true, showSymbol: false, areaStyle: { opacity: 0.05 }, data: props.points.map((p) => p.normal) },
      { name: '경고', type: 'line', smooth: true, showSymbol: true, data: props.points.map((p) => p.warning) },
      { name: '장애', type: 'line', smooth: true, showSymbol: true, data: props.points.map((p) => p.error) },
    ],
  })
}
watch([() => props.points, chartEl], () => {
  if (!chartEl.value) {
    observer?.disconnect()
    observer = null
    chart?.dispose()
    chart = null
    return
  }
  if (!chart) {
    chart = echarts.init(chartEl.value)
    observer = new ResizeObserver(() => chart?.resize())
    observer.observe(chartEl.value)
  }
  render()
}, { flush: 'post' })
onUnmounted(() => { observer?.disconnect(); chart?.dispose() })
</script>
<template><div v-if="points.length" ref="chartEl" class="event-chart" role="img" aria-label="시간별 정상 메시지, 경고, 장애 발생 추이"></div><el-empty v-else description="차트 데이터가 없습니다" /></template>
