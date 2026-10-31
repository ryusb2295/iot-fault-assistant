<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { dataMode, getEvent, getEventLogs, getManuals, getCases, getLocalResponse, saveEventResponse } from '../services/api'
import { eventTypes } from '../data/mockData'
import { formatTime, formatDuration } from '../utils/format'
import StatusBadge from '../components/StatusBadge.vue'
import ChecklistPanel from '../components/ChecklistPanel.vue'

const route = useRoute()
const event = ref(null)
const logs = ref([])
const manuals = ref([])
const cases = ref([])
const checked = ref([])
const action = ref('')
const completeAction = ref(false)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
let pollTimer
let mounted = false
const relatedManuals = computed(() => manuals.value.filter((item) => item.type === event.value?.type))
const relatedCases = computed(() => cases.value.filter((item) => item.type === event.value?.type))
const steps = computed(() => relatedManuals.value[0]?.steps || [])
const actionStatusLabel = computed(() => event.value?.actionStatus === 'completed' || event.value?.status === 'resolved' ? '조치 완료' : event.value?.actionStatus === 'in_progress' || event.value?.actions?.length ? '점검 중' : '미조치')
const load = async (id) => {
  loading.value = true; error.value = ''
  try {
    const [item, eventLogs, manualRows, caseRows] = await Promise.all([getEvent(id), getEventLogs(id), getManuals(), getCases()])
    if (!mounted) return
    event.value = item
    logs.value = eventLogs
    manuals.value = manualRows
    cases.value = caseRows
    const saved = dataMode === 'api' ? event.value?.actions?.[0] : getLocalResponse(id)
    checked.value = saved?.checklist || saved?.checked || []
    action.value = saved?.actionText || saved?.action || ''
    completeAction.value = Boolean(saved?.resolved || event.value?.status === 'resolved')
  } catch { error.value = '백엔드 연결 실패: 장애 상세 정보를 불러오지 못했습니다.' }
  finally { if (mounted) loading.value = false }
}
const refresh = async () => {
  try {
    const [item, eventLogs] = await Promise.all([getEvent(route.params.id), getEventLogs(route.params.id)])
    if (mounted) { event.value = item; logs.value = eventLogs; error.value = '' }
  } catch { if (mounted) error.value = '백엔드 연결 실패: 장애 상세 정보를 갱신하지 못했습니다.' }
  finally { if (mounted) pollTimer = setTimeout(refresh, 2000) }
}
onMounted(async () => {
  mounted = true
  await load(route.params.id)
  if (mounted) pollTimer = setTimeout(refresh, 2000)
})
onUnmounted(() => { mounted = false; clearTimeout(pollTimer) })
const save = async () => {
  if (!action.value.trim()) { ElMessage.warning('최종 조치 결과를 입력해 주세요.'); return }
  saving.value = true
  try { await saveEventResponse(event.value.id, { checked: checked.value, action: action.value.trim(), resolved: completeAction.value, savedAt: new Date().toISOString() }); ElMessage.success(dataMode === 'api' ? '조치 기록을 DB에 저장했습니다.' : '실습용 조치 기록을 저장했습니다.') }
  catch { ElMessage.error('조치 기록을 저장하지 못했습니다.') }
  finally { saving.value = false }
}
</script>
<template>
  <div v-loading="loading" class="page-stack"><div class="page-intro"><div><RouterLink to="/events" class="back-link">← 장애 이력으로 돌아가기</RouterLink><h2>장애 상세 및 대응</h2><p v-if="event">{{ event.id }} · {{ event.summary }}</p></div><StatusBadge v-if="event" :kind="event.status === 'resolved' ? 'success' : 'warning'" :label="actionStatusLabel" /></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <el-empty v-else-if="!event && !loading" description="해당 장애 이력을 찾을 수 없습니다" />
    <template v-else-if="event">
      <section class="panel"><div class="section-head"><div><h3>장애 기본 정보</h3><p>{{ dataMode === 'mock' ? 'Python 규칙 기반 판정 결과의 실습용 예시' : 'Python 규칙 엔진의 실제 판정 기록' }}</p></div><StatusBadge :kind="event.type === 'response_delay' ? 'warning' : 'danger'" :label="eventTypes[event.type]" /></div><dl class="detail-list detail-grid"><div><dt>장애 ID</dt><dd>{{ event.id }}</dd></div><div><dt>장치 ID</dt><dd>{{ event.deviceId }}</dd></div><div><dt>발생 시각</dt><dd>{{ formatTime(event.occurredAt) }}</dd></div><div><dt>복구 시각</dt><dd>{{ formatTime(event.recoveredAt) }}</dd></div><div><dt>지속 시간</dt><dd>{{ formatDuration(event.durationSeconds) }}</dd></div><div><dt>복구 상태</dt><dd>{{ event.recoveredAt ? '복구됨' : '미복구' }}</dd></div><div><dt>조치 상태</dt><dd>{{ actionStatusLabel }}</dd></div></dl></section>
      <div class="two-col"><section class="panel"><div class="section-head"><div><h3>관련 통신 로그</h3><p>{{ dataMode === 'mock' ? '장애 시점 전후의 예시 로그' : 'SQLite에 저장된 MQTT 로그' }}</p></div></div><div v-if="logs.length" class="log-list"><div v-for="log in logs" :key="`${log.time}-${log.message}`" class="log-row"><time>{{ formatTime(log.time) }}</time><StatusBadge :kind="log.level === '장애' ? 'danger' : log.level === '경고' ? 'warning' : 'info'" :label="log.level" /><span>{{ log.message }}</span></div></div><el-empty v-else description="이 장애에 연결된 로그가 없습니다" /></section>
      <section class="panel"><div class="section-head"><div><h3>관련 매뉴얼</h3><p>장애 유형에 따라 검색된 실습용 문서</p></div><RouterLink class="text-link" to="/knowledge">전체 보기 →</RouterLink></div><div v-for="manual in relatedManuals" :key="manual.id" class="knowledge-mini"><strong>{{ manual.title }}</strong><small>{{ manual.id }} · 갱신 {{ manual.updatedAt }}</small><ol><li v-for="step in manual.steps" :key="step">{{ step }}</li></ol></div><el-empty v-if="!relatedManuals.length" description="관련 매뉴얼이 없습니다" /></section></div>
      <div class="two-col"><section class="panel"><div class="section-head"><div><h3>과거 조치 사례</h3><p>같은 유형의 실습용 사례</p></div></div><div v-for="item in relatedCases" :key="item.id" class="knowledge-mini"><strong>{{ item.title }}</strong><small>{{ item.id }} · {{ item.date }}</small><p>{{ item.action }}</p></div><el-empty v-if="!relatedCases.length" description="관련 사례가 없습니다" /></section>
      <section class="panel ai-panel"><div class="section-head"><div><h3>AI 점검 설명 <span class="example-label">예시 설명</span></h3><p>실제 LLM은 아직 연결되지 않았습니다.</p></div></div><p>이 장애는 <strong>{{ eventTypes[event.type] }}</strong> 유형입니다. 위 매뉴얼의 점검 순서와 과거 조치 사례를 참고하여 통신 상태를 확인하세요. 점검 결과와 최종 조치는 담당자가 직접 기록합니다.</p><div class="info-note">이 문장은 화면 시연용 고정 예시입니다. AI가 장애를 판정하거나 장치를 제어하지 않습니다.</div></section></div>
      <div class="two-col"><section class="panel"><div class="section-head"><div><h3>사용자 점검 체크리스트</h3><p>확인한 항목을 선택하고 조치 결과와 함께 저장하세요.</p></div><span class="section-meta">{{ checked.length }} / {{ steps.length }} 완료</span></div><ChecklistPanel v-model="checked" :steps="steps" /></section>
      <section class="panel"><div class="section-head"><div><h3>최종 조치 결과</h3><p>{{ dataMode === 'api' ? '조치 기록은 SQLite에 저장됩니다. 조치 완료 여부와 통신 복구 여부는 별도로 관리합니다.' : '실습 모드에서는 현재 브라우저에만 저장됩니다.' }}</p></div></div><el-input v-model="action" type="textarea" :rows="5" maxlength="1000" show-word-limit placeholder="점검 결과와 실제 수행한 조치를 입력하세요" aria-label="최종 조치 결과" /><el-checkbox v-model="completeAction" :disabled="event.status === 'resolved'">사용자 조치 완료로 기록</el-checkbox><div class="form-actions"><el-button type="primary" :loading="saving" @click="save">조치 기록 저장</el-button></div></section></div>
    </template>
  </div>
</template>
