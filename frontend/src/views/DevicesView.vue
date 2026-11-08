<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { dataMode, getDevices } from '../services/api'
import { formatTime, formatElapsed } from '../utils/format'
import DeviceStatusCard from '../components/DeviceStatusCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
const devices = ref([])
const device = computed(() => devices.value.find((item) => item.id === 'RPI-01') || null)
const loading = ref(true)
const error = ref('')
const now = ref(Date.now())
let timer
let pollTimer
let mounted = false
const elapsed = computed(() => formatElapsed(device.value?.lastReceivedAt, now.value))
const poll = async () => {
  try {
    const rows = await getDevices()
    if (mounted) { devices.value = rows; error.value = '' }
  } catch { if (mounted) error.value = '백엔드 연결 실패: 설비 목록을 불러오지 못했습니다.' }
  finally { if (mounted) { loading.value = false; pollTimer = setTimeout(poll, 2000) } }
}
onMounted(() => {
  mounted = true
  timer = setInterval(() => { now.value = Date.now() }, 1000)
  poll()
})
onUnmounted(() => { mounted = false; clearInterval(timer); clearTimeout(pollTimer) })
</script>
<template>
  <div v-loading="loading" class="page-stack workspace-page"><div class="page-intro"><div><span class="eyebrow">DEVICE MONITORING</span><h2>설비 모니터링</h2><p>등록된 설비의 통신 상태와 최근 수신 메시지입니다.</p></div><StatusBadge kind="info" :label="`${devices.length}대 등록`" /></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <template v-else-if="device"><section class="panel"><div class="section-head"><div><h3>등록 설비 목록</h3><p>{{ dataMode === 'mock' ? '실습용 설비' : '등록된 설비 · 2초마다 갱신' }}</p></div></div><div class="table-scroll"><el-table class="device-table" :data="devices" empty-text="등록된 설비가 없습니다"><el-table-column prop="id" label="장치 ID" min-width="120" /><el-table-column prop="name" label="설비명" min-width="180" /><el-table-column label="통신 상태" min-width="110"><template #default="scope"><StatusBadge :kind="scope.row.status === 'normal' ? 'success' : scope.row.status === 'unknown' ? 'info' : 'danger'" :label="scope.row.status === 'normal' ? '정상' : scope.row.status === 'unknown' ? '수신 대기' : '장애'" /></template></el-table-column><el-table-column label="마지막 수신" min-width="180"><template #default="scope">{{ formatTime(scope.row.lastReceivedAt) }}</template></el-table-column></el-table></div></section><section class="panel"><div class="section-head"><div><h3>RPI-01 통신 상태</h3><p>{{ dataMode === 'mock' ? '실습용 모의 데이터' : '실시간 통신 상태 · 2초마다 갱신' }}</p></div></div><DeviceStatusCard :device="device" :now="now" /></section>
      <div class="two-col"><section class="panel"><div class="section-head"><h3>장치 상세 정보</h3></div><dl class="detail-list"><div><dt>장치 ID</dt><dd>{{ device.id }}</dd></div><div><dt>현재 상태</dt><dd><StatusBadge :kind="device.status === 'normal' ? 'success' : device.status === 'unknown' ? 'info' : 'danger'" :label="device.status === 'normal' ? '정상' : device.status === 'unknown' ? '수신 대기' : '장애'" /></dd></div><div><dt>마지막 수신 시각</dt><dd>{{ formatTime(device.lastReceivedAt) }}</dd></div><div><dt>마지막 수신 이후</dt><dd>{{ elapsed }}</dd></div><div><dt>메시지 수신 주기</dt><dd>{{ device.intervalSeconds }}초</dd></div><div><dt>구독 Topic</dt><dd><code>{{ device.topic }}</code></dd></div></dl></section>
      <section class="panel"><div class="section-head"><div><h3>최근 수신 메시지</h3><p>{{ dataMode === 'mock' ? '실습용 JSON payload' : 'MQTT에서 수신한 JSON payload' }}</p></div></div><pre class="code-block">{{ JSON.stringify(device.recentMessage, null, 2) }}</pre><div class="info-note">{{ dataMode === 'mock' ? '메시지 수신 중단·응답 지연·형식 오류는 실제로 판정하지 않습니다.' : '장애 판정은 Python 수신 프로세스에서 수행합니다.' }}</div></section></div></template><el-empty v-else-if="!loading" description="등록된 설비가 없습니다" />
  </div>
</template>
