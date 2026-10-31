<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Monitor, CircleCheck, Warning, Bell } from '@element-plus/icons-vue'
import { dataMode, getDashboard, getDevice, getEvents, getRecentActions, getChartPoints } from '../services/api'
import { eventTypes } from '../data/mockData'
import { formatTime } from '../utils/format'
import StatCard from '../components/StatCard.vue'
import DeviceStatusCard from '../components/DeviceStatusCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import EventChart from '../components/EventChart.vue'

const loading = ref(true)
const error = ref('')
const dashboard = ref({ devices: 0, normalDevices: 0, faults: 0, unrecoveredFaults: 0, unresolvedFaults: 0 })
const device = ref(null)
const events = ref([])
const actions = ref([])
const points = ref([])
const chartUpdatedAt = ref(null)
const chartError = ref(false)
const dashboardLoaded = ref(false)
const now = ref(Date.now())
let timer
let pollTimer
let mounted = false
let actionsLoaded = false
const poll = async () => {
  try {
    const [counts, currentDevice, recentEvents, chartPoints, recentActions] = await Promise.allSettled([
      getDashboard(), getDevice(), getEvents(), getChartPoints(),
      actionsLoaded ? Promise.resolve(null) : getRecentActions(),
    ])
    if (!mounted) return
    if (counts.status === 'fulfilled') dashboard.value = counts.value
    if (currentDevice.status === 'fulfilled') device.value = currentDevice.value
    if (recentEvents.status === 'fulfilled') events.value = recentEvents.value
    if ([counts, currentDevice, recentEvents].every((result) => result.status === 'fulfilled')) {
      dashboardLoaded.value = true
      error.value = ''
    } else {
      error.value = '백엔드 연결 실패: 대시보드 데이터를 갱신하지 못했습니다.'
    }
    if (chartPoints.status === 'fulfilled') {
      points.value = chartPoints.value
      chartUpdatedAt.value = Date.now()
      chartError.value = false
    } else chartError.value = true
    if (!actionsLoaded && recentActions.status === 'fulfilled') {
      actions.value = recentActions.value
      actionsLoaded = true
    }
  } catch {
    if (mounted) { error.value = '백엔드 연결 실패: 대시보드 데이터를 갱신하지 못했습니다.'; chartError.value = true }
  }
  finally {
    if (mounted) { loading.value = false; pollTimer = setTimeout(poll, 2000) }
  }
}
onMounted(() => {
  mounted = true
  timer = setInterval(() => { now.value = Date.now() }, 1000)
  poll()
})
onUnmounted(() => { mounted = false; clearInterval(timer); clearTimeout(pollTimer) })
</script>
<template>
  <div v-loading="loading" class="page-stack">
    <div class="page-intro"><div><span class="eyebrow">OVERVIEW</span><h2>통신 운영 현황</h2><p>RPI-01 한 대의 {{ dataMode === 'mock' ? '실습용' : '실제 수신' }} 통신 상태와 장애 이력을 확인합니다.</p></div><RouterLink to="/events" class="el-button el-button--primary">장애 이력 보기</RouterLink></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <template v-if="dashboardLoaded">
      <div class="stat-grid">
        <StatCard label="등록 설비 수" :value="dashboard.devices" unit="대" note="등록된 장치" tone="blue" :icon="Monitor" />
        <StatCard label="정상 설비 수" :value="dashboard.normalDevices" unit="대" :note="dataMode === 'mock' ? '현재 모의 상태 기준' : 'SQLite 저장 상태 기준'" tone="green" :icon="CircleCheck" />
        <StatCard label="장애 발생 수" :value="dashboard.faults" :note="dataMode === 'mock' ? '실습용 전체 이력' : 'SQLite 전체 이력'" tone="red" :icon="Warning" />
        <StatCard label="조치 미완료 수" :value="dashboard.unresolvedFaults" :note="dashboard.unrecoveredFaults == null ? '미복구 집계 대기' : `미복구 기록 ${dashboard.unrecoveredFaults}건`" tone="orange" :icon="Bell" />
      </div>
      <div class="dashboard-grid">
        <section class="panel"><div class="section-head"><div><h3>실시간 설비 통신 상태</h3><p>{{ dataMode === 'mock' ? '실습용 모의 데이터' : '로컬 MQTT 수신 결과 · 2초마다 갱신' }}</p></div><RouterLink class="text-link" to="/devices">자세히 보기 →</RouterLink></div><DeviceStatusCard v-if="device" :device="device" :now="now" /><el-empty v-else description="등록된 설비가 없습니다" /></section>
        <section class="panel"><div class="section-head"><div><h3>최근 장애 발생</h3><p>RPI-01 장애 이력</p></div><RouterLink class="text-link" to="/events">전체 보기 →</RouterLink></div><div v-if="events.length" class="compact-list"><RouterLink v-for="event in events.slice(0, 3)" :key="event.id" :to="`/events/${event.id}`" class="compact-row"><div><strong>{{ eventTypes[event.type] }}</strong><small>{{ event.id }} · {{ formatTime(event.occurredAt) }}</small></div><StatusBadge :kind="event.status === 'resolved' ? 'success' : 'warning'" :label="event.status === 'resolved' ? '조치 완료' : '조치 미완료'" /></RouterLink></div><el-empty v-else description="장애 이력이 없습니다" /></section>
        <section class="panel"><div class="section-head"><div><h3>통신 이벤트 추이</h3><p>{{ dataMode === 'mock' ? '실습용 시간별 메시지 집계' : '최근 7시간 · 정상: 유효 상태 수신 / 경고: 형식 오류 로그 / 장애: 신규 장애 판정' }}</p></div><span class="section-meta">{{ dataMode === 'mock' ? '오늘' : '최근 7시간' }}</span></div><EventChart :points="points" /><div class="chart-refresh-meta"><span>최근 데이터 갱신: {{ chartUpdatedAt ? formatTime(chartUpdatedAt) : '대기 중' }}</span><span>자동 갱신: 2초</span><span :class="chartError ? 'is-error' : 'is-ok'">{{ dataMode === 'mock' ? '실습용 모의 데이터' : chartError ? 'API 갱신 실패 · 마지막 성공 데이터 표시' : chartUpdatedAt ? 'API 연결 정상' : 'API 연결 확인 중' }}</span></div></section>
        <section class="panel"><div class="section-head"><div><h3>최근 조치 내역</h3><p>과거 조치 사례 요약</p></div><RouterLink class="text-link" to="/knowledge">사례 보기 →</RouterLink></div><div v-if="actions.length" class="action-list"><div v-for="action in actions" :key="action.eventId" class="action-row"><div class="action-symbol">✓</div><div><strong>{{ action.action }}</strong><small>{{ action.eventId }} · {{ formatTime(action.time) }}</small></div></div></div><el-empty v-else description="조치 내역이 없습니다" /></section>
      </div>
    </template>
  </div>
</template>
