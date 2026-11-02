<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { dataMode, connectionState, monitoringState, getHealth } from '../services/api'

const route = useRoute()
const now = ref(Date.now())
let timer
let healthTimer
onMounted(() => {
  getHealth().catch(() => {})
  timer = setInterval(() => { now.value = Date.now() }, 1000)
  healthTimer = setInterval(() => getHealth().catch(() => {}), 5000)
})
onUnmounted(() => clearInterval(timer))
onUnmounted(() => clearInterval(healthTimer))
const clock = computed(() => new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeStyle: 'medium' }).format(now.value))
const systemLabel = computed(() => {
  if (dataMode === 'mock') return '실습용 모의 데이터'
  if (connectionState.value === 'error') return '백엔드 연결 실패'
  if (!monitoringState.value) return '시스템 상태 확인 중'
  const state = monitoringState.value
  if (state.worker !== 'running') return 'MQTT Worker 중단'
  if (state.broker !== 'connected') return 'MQTT Broker 연결 끊김'
  if (state.deviceHeartbeat === 'timeout') return '장치 상태 메시지 미수신 · 원인 미확인'
  if (state.deviceHeartbeat !== 'normal') return '장치 상태 메시지 대기'
  return 'PC MQTT 시뮬레이터 통신 정상'
})
</script>

<template>
  <header class="app-header">
    <div class="header-heading"><span class="header-eyebrow">운영 현황 / {{ route.meta.title }}</span><h1>{{ route.meta.title }}</h1></div>
    <div class="header-meta"><span class="demo-pill">{{ systemLabel }}</span><time>{{ clock }}</time><span class="system-state"><i></i>{{ dataMode === 'mock' ? '데모 화면 정상' : connectionState === 'connected' ? 'API 연결 정상' : 'API 연결 확인 중' }}</span></div>
  </header>
</template>
