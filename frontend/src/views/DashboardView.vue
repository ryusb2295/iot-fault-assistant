<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { dataMode, getDashboard, getDevice, getEvents, getRecentActions, getChartPoints } from '../services/api'
import { eventTypes } from '../data/mockData'
import { formatTime, formatElapsed } from '../utils/format'
import { computed } from 'vue'
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
const dashboardUpdatedAt = ref(null)
const chartError = ref(false)
const dashboardLoaded = ref(false)
const now = ref(Date.now())
// 대시보드 상단: 장치 하나의 "지금 상태"를 한눈에 보여주기 위한 값
const TIMEOUT_SECONDS = 10
const elapsedSeconds = computed(() => device.value?.lastReceivedAt ? Math.max(0, (now.value - new Date(device.value.lastReceivedAt).getTime()) / 1000) : null)
const gaugePercent = computed(() => elapsedSeconds.value == null ? 0 : Math.min(100, elapsedSeconds.value / TIMEOUT_SECONDS * 100))
const live = computed(() => {
  const status = device.value?.status
  if (status === 'normal') return { tone: 'ok', title: '정상 수신 중', note: '2초마다 상태 메시지를 받고 있습니다' }
  if (status === 'fault') return { tone: 'bad', title: '통신 끊김', note: '10초 넘게 상태 메시지가 없어 장애로 판정했습니다' }
  return { tone: 'unknown', title: '상태 확인 불가', note: '감시 시스템(Worker/Broker) 연결을 확인하세요' }
})
const gaugeTone = computed(() => live.value.tone === 'bad' ? 'bad' : gaugePercent.value >= 50 ? 'warn' : 'ok')
const activeFaults = computed(() => dashboard.value.unrecoveredFaults ?? 0)
let timer
let pollTimer
let mounted = false
const poll = async () => {
  try {
    const [counts, currentDevice, recentEvents, chartPoints, recentActions] = await Promise.allSettled([
      getDashboard(), getDevice(), getEvents(), getChartPoints(),
      getRecentActions(),
    ])
    if (!mounted) return
    if (counts.status === 'fulfilled') dashboard.value = counts.value
    if (currentDevice.status === 'fulfilled') device.value = currentDevice.value
    if (recentEvents.status === 'fulfilled') events.value = recentEvents.value
    if ([counts, currentDevice, recentEvents].every((result) => result.status === 'fulfilled')) {
      dashboardLoaded.value = true
      dashboardUpdatedAt.value = Date.now()
      error.value = ''
    } else {
      error.value = '백엔드 연결 실패: 대시보드 데이터를 갱신하지 못했습니다.'
    }
    if (chartPoints.status === 'fulfilled') {
      points.value = chartPoints.value
      chartUpdatedAt.value = Date.now()
      chartError.value = false
    } else chartError.value = true
    if (recentActions.status === 'fulfilled') actions.value = recentActions.value
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
  <div v-loading="loading" class="page-stack dashboard-page">
    <div class="page-intro"><div><span class="eyebrow">OPERATIONS OVERVIEW</span><h2>통신 운영 현황</h2><p>RPI-01 한 대의 {{ dataMode === 'mock' ? '실습용' : '실제 수신' }} 통신 상태와 장애 이력을 확인합니다.</p></div><RouterLink to="/events" class="el-button el-button--primary">장애 이력 보기</RouterLink></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <template v-if="dashboardLoaded">
      <section class="live-hero" aria-label="RPI-01 실시간 상태">
        <div :class="['panel', 'live-panel', `live-${live.tone}`]">
          <div class="live-top"><span class="live-dot" aria-hidden="true"></span><div><span class="live-eyebrow">RPI-01 · PC MQTT 시뮬레이터</span><h3>{{ live.title }}</h3><p>{{ live.note }}</p></div><RouterLink class="text-link" to="/devices">장치 상세 →</RouterLink></div>
          <div class="live-counter"><span class="live-label">마지막 수신 후</span><strong>{{ device?.lastReceivedAt ? formatElapsed(device.lastReceivedAt, now) : '—' }}</strong></div>
          <div class="live-gauge" role="meter" :aria-valuenow="Math.round(elapsedSeconds ?? 0)" aria-valuemin="0" aria-valuemax="10" aria-label="장애 판정까지 경과 시간"><span :class="`gauge-${gaugeTone}`" :style="{ width: `${gaugePercent}%` }"></span><i style="left: 20%"></i><em>2초 주기</em><em class="end">10초 → 장애 판정</em></div>
          <div class="live-meta"><span>마지막 수신 <b>{{ formatTime(device?.lastReceivedAt) }}</b></span><span>Topic <code>{{ device?.topic }}</code></span></div>
        </div>
        <div class="kpi-stack">
          <RouterLink to="/events" :class="['panel', 'kpi', activeFaults > 0 ? 'kpi-bad' : 'kpi-ok']"><span>진행 중 장애</span><strong>{{ activeFaults }}<small>건</small></strong><em>{{ activeFaults > 0 ? '통신이 아직 돌아오지 않은 장애' : '모든 장애가 통신 정상화됨' }}</em></RouterLink>
          <RouterLink to="/events" :class="['panel', 'kpi', dashboard.unresolvedFaults > 0 ? 'kpi-warn' : 'kpi-ok']"><span>점검 기록 필요</span><strong>{{ dashboard.unresolvedFaults }}<small>건</small></strong><em>사람이 원인과 조치를 아직 기록하지 않은 장애</em></RouterLink>
          <RouterLink to="/events" class="panel kpi"><span>누적 장애</span><strong>{{ dashboard.faults }}<small>건</small></strong><em>중단 {{ dashboard.faultsByType?.CONNECTION_TIMEOUT ?? 0 }} · 지연 {{ dashboard.faultsByType?.RESPONSE_DELAY ?? 0 }} · 형식 {{ dashboard.faultsByType?.INVALID_MESSAGE ?? 0 }}</em></RouterLink>
        </div>
      </section>
      <div class="dashboard-grid">
        <section class="panel"><div class="section-head"><div><h3>최근 장애</h3><p>통신 상태와 점검 기록을 따로 표시</p></div><RouterLink class="text-link" to="/events">전체 보기 →</RouterLink></div><div v-if="events.length" class="compact-list"><RouterLink v-for="event in events.slice(0, 5)" :key="event.id" :to="`/events/${event.id}`" class="compact-row"><div><strong><span :class="['type-dot', `type-${event.type}`]" aria-hidden="true"></span>{{ eventTypes[event.type] }}</strong><small>#{{ event.id }} · {{ formatTime(event.occurredAt) }}</small></div><span class="badge-pair"><StatusBadge :kind="event.recoveredAt ? 'success' : 'danger'" :label="event.recoveredAt ? '통신 정상화' : '통신 끊김'" /><StatusBadge :kind="event.status === 'resolved' ? 'success' : 'warning'" :label="event.status === 'resolved' ? '점검 기록 완료' : '점검 기록 필요'" /></span></RouterLink></div><el-empty v-else :image-size="60" description="장애 이력이 없습니다" /></section>
        <section class="panel"><div class="section-head"><div><h3>통신 이벤트 추이</h3><p>{{ dataMode === 'mock' ? '실습용 시간별 메시지 집계' : '최근 15분 · 1분 단위 (정상이면 분당 약 30건)' }}</p></div><span :class="['section-meta', chartError ? 'is-error' : '']">{{ chartError ? '갱신 실패' : '2초마다 갱신' }}</span></div><EventChart :points="points" /></section>
      </div>
      <section class="panel"><div class="section-head"><div><h3>최근 조치 기록</h3><p>DB에 저장된 실제 점검 기록 · 같은 유형의 다음 장애에서 다시 보여줍니다</p></div><RouterLink class="text-link" to="/knowledge">전체 기록 →</RouterLink></div><div v-if="actions.length" class="action-grid"><RouterLink v-for="action in actions.slice(0, 4)" :key="action.id ?? `${action.eventId}-${action.time}`" :to="`/events/${action.eventId}`" class="action-row"><div class="action-symbol">✓</div><div><strong>{{ action.action }}</strong><small>{{ action.type ? eventTypes[action.type] + ' · ' : '' }}#{{ action.eventId }} · {{ formatTime(action.time) }}</small></div></RouterLink></div><el-empty v-else :image-size="56" description="아직 저장된 점검 기록이 없습니다" /></section>
    </template>
  </div>
</template>
