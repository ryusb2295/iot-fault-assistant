<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { dataMode, connectionState } from '../services/api'

const route = useRoute()
const now = ref(Date.now())
let timer
onMounted(() => { timer = setInterval(() => { now.value = Date.now() }, 1000) })
onUnmounted(() => clearInterval(timer))
const clock = computed(() => new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeStyle: 'medium' }).format(now.value))
</script>

<template>
  <header class="app-header">
    <div class="header-heading"><span class="header-eyebrow">운영 현황 / {{ route.meta.title }}</span><h1>{{ route.meta.title }}</h1></div>
    <div class="header-meta"><span class="demo-pill">{{ dataMode === 'mock' ? '실습용 모의 데이터' : connectionState === 'connected' ? '로컬 MQTT 연동 데이터' : connectionState === 'error' ? '백엔드 연결 실패' : '백엔드 연결 확인 중' }}</span><time>{{ clock }}</time><span class="system-state"><i></i>{{ dataMode === 'mock' ? '데모 화면 정상' : connectionState === 'connected' ? 'API 연결 정상' : 'API 상태 확인' }}</span></div>
  </header>
</template>
