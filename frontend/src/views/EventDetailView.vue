<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { dataMode, getEvent, getEventLogs, getManuals, getCases, getAiGuidance, getLocalResponse, saveEventResponse } from '../services/api'
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
const aiGuidance = ref(null)
const aiLoading = ref(false)
let pollTimer
let mounted = false
const relatedManuals = computed(() => manuals.value.filter((item) => item.type === event.value?.type))
const relatedCases = computed(() => cases.value.filter((item) => item.type === event.value?.type))
const steps = computed(() => relatedManuals.value[0]?.steps || [])
const actionStatusLabel = computed(() => event.value?.actionStatus === 'completed' || event.value?.status === 'resolved' ? '조치 완료' : event.value?.actionStatus === 'in_progress' || event.value?.actions?.length ? '점검 중' : '미조치')
const loadAiGuidance = async (id) => {
  if (dataMode === 'mock') return
  aiLoading.value = true
  aiGuidance.value = null
  try { const result = await getAiGuidance(id); if (mounted && String(route.params.id) === String(id)) aiGuidance.value = result }
  catch { if (mounted) aiGuidance.value = { status: 'unavailable', answer: '로컬 AI 점검 안내를 불러오지 못했습니다. 장애 판정과 로그는 계속 확인할 수 있습니다.', sources: [] } }
  finally { if (mounted) aiLoading.value = false }
}
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
    loadAiGuidance(id)
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
      <div class="two-col"><section class="panel"><div class="section-head"><div><h3>실습용 조치 사례</h3><p>실제 장애 이력에서 검색한 사례가 아닌 예시 데이터</p></div></div><div v-for="item in relatedCases" :key="item.id" class="knowledge-mini"><strong>{{ item.title }}</strong><small>{{ item.id }} · {{ item.date }}</small><p>{{ item.action }}</p></div><el-empty v-if="!relatedCases.length" description="관련 사례가 없습니다" /></section>
      <section class="panel ai-panel"><div class="section-head"><div><h3>AI 점검 안내 <span v-if="dataMode === 'mock'" class="example-label">실습 모드</span><span v-else-if="aiGuidance?.status === 'ready'" class="example-label">Ollama 실제 응답</span></h3><p>규칙 엔진의 장애 판정과 별개로 참고하는 점검 안내</p></div><el-button v-if="dataMode === 'api'" :loading="aiLoading" @click="loadAiGuidance(event.id)">다시 생성</el-button></div><p v-if="dataMode === 'mock'">실습 모드에서는 실제 AI 답변을 생성하지 않습니다.</p><p v-else-if="aiLoading">로컬 모델이 매뉴얼과 로그를 검토하고 있습니다.</p><template v-else-if="aiGuidance"><p class="ai-answer">{{ aiGuidance.answer }}</p><div v-if="aiGuidance.sources?.length" class="ai-sources"><strong>검색된 근거 문서</strong><ul><li v-for="source in aiGuidance.sources" :key="`${source.path}:${source.lineStart}`">{{ source.title }} · {{ source.section }} ({{ source.path }}:{{ source.lineStart }}–{{ source.lineEnd }})</li></ul></div></template><div class="info-note">실제 장애 유형과 복구 상태는 Python 규칙 엔진 및 수신 로그의 기록입니다. AI 안내는 원인을 확정하거나 장치를 제어하지 않습니다.</div></section></div>
      <div class="two-col"><section class="panel"><div class="section-head"><div><h3>사용자 점검 체크리스트</h3><p>확인한 항목을 선택하고 조치 결과와 함께 저장하세요.</p></div><span class="section-meta">{{ checked.length }} / {{ steps.length }} 완료</span></div><ChecklistPanel v-model="checked" :steps="steps" /></section>
      <section class="panel"><div class="section-head"><div><h3>최종 조치 결과</h3><p>{{ dataMode === 'api' ? '조치 기록은 SQLite에 저장됩니다. 조치 완료 여부와 통신 복구 여부는 별도로 관리합니다.' : '실습 모드에서는 현재 브라우저에만 저장됩니다.' }}</p></div></div><el-input v-model="action" type="textarea" :rows="5" maxlength="1000" show-word-limit placeholder="점검 결과와 실제 수행한 조치를 입력하세요" aria-label="최종 조치 결과" /><el-checkbox v-model="completeAction" :disabled="event.status === 'resolved'">사용자 조치 완료로 기록</el-checkbox><div class="form-actions"><el-button type="primary" :loading="saving" @click="save">조치 기록 저장</el-button></div></section></div>
    </template>
  </div>
</template>
