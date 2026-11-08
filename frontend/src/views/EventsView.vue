<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { dataMode, getEvents } from '../services/api'
import EventTable from '../components/EventTable.vue'
const events = ref([])
const loading = ref(true)
const error = ref('')
const query = ref('')
const type = ref('')
const status = ref('')
const page = ref(1)
const pageSize = 10
let pollTimer
let mounted = false
const filtered = computed(() => events.value.filter((event) =>
  (!type.value || event.type === type.value) &&
  (!status.value || event.status === status.value) &&
  (!query.value || `${event.id} ${event.deviceId} ${event.summary}`.toLowerCase().includes(query.value.trim().toLowerCase()))
))
const pageRows = computed(() => filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize))
watch([query, type, status], () => { page.value = 1 })
const poll = async () => {
  try {
    const rows = await getEvents()
    if (mounted) { events.value = rows; error.value = '' }
  } catch { if (mounted) error.value = '백엔드 연결 실패: 장애 이력을 불러오지 못했습니다.' }
  finally { if (mounted) { loading.value = false; pollTimer = setTimeout(poll, 2000) } }
}
onMounted(() => { mounted = true; poll() })
onUnmounted(() => { mounted = false; clearTimeout(pollTimer) })
</script>
<template>
  <div class="page-stack workspace-page"><div class="page-intro"><div><span class="eyebrow">EVENT HISTORY</span><h2>장애 이력</h2><p>{{ dataMode === 'mock' ? '규칙 기반 장애 판정 결과의 실습용 이력을 조회합니다.' : 'Python 규칙 엔진이 기록한 장애 이력을 조회합니다.' }}</p></div></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <section v-else class="panel"><div class="section-head"><div><h3>전체 장애 목록</h3><p>총 {{ filtered.length }}건 · 설비 RPI-01</p></div><span class="section-meta">{{ dataMode === 'mock' ? '실습용 데이터' : 'SQLite 기록' }}</span></div>
      <div class="filter-bar"><el-input v-model="query" placeholder="장애 ID, 장치 ID, 내용 검색" clearable class="search-input" :prefix-icon="Search" aria-label="장애 검색" /><el-select v-model="type" placeholder="장애 유형 전체" clearable aria-label="장애 유형 필터"><el-option label="메시지 수신 중단" value="message_timeout" /><el-option label="응답 지연" value="response_delay" /><el-option label="메시지 형식 오류" value="format_error" /></el-select><el-select v-model="status" placeholder="점검 기록 전체" clearable aria-label="점검 기록 필터"><el-option label="점검 기록 필요" value="open" /><el-option label="점검 기록 완료" value="resolved" /></el-select></div>
      <EventTable :rows="pageRows" :loading="loading" /><div class="pagination-row"><span>총 {{ filtered.length }}건</span><el-pagination v-model:current-page="page" layout="prev, pager, next" :total="filtered.length" :page-size="pageSize" background /></div>
    </section>
  </div>
</template>
