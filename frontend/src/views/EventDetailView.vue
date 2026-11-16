<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import MarkdownIt from 'markdown-it'
import { dataMode, getEvent, getEventLogs, getManuals, getCases, getAiGuidance, getLocalResponse, saveEventResponse, getPastActions } from '../services/api'
import { operatorGuidance, operatorTitle } from '../data/operatorGuidance'
import { formatTime, formatDuration } from '../utils/format'
import ChecklistPanel from '../components/ChecklistPanel.vue'

const route = useRoute()
const event = ref(null)
const logs = ref([])
const manuals = ref([])
const cases = ref([])
const pastActions = ref([])
const checked = ref([])
const action = ref('')
const completeAction = ref(false)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const aiGuidance = ref(null)
const aiLoading = ref(false)
const renderedAiAnswer = computed(() => new MarkdownIt({ html: false, linkify: false, breaks: true }).render(aiGuidance.value?.answer || ''))
const guide = computed(() => operatorGuidance[event.value?.type])
const steps = computed(() => guide.value?.steps ?? [])
const relatedManuals = computed(() => manuals.value.filter(item => item.type === event.value?.type))
const relatedCases = computed(() => cases.value.filter(item => item.type === event.value?.type))
const actionStatusLabel = computed(() => event.value?.actionStatus === 'completed' || event.value?.status === 'resolved'
  ? '점검 기록 완료'
  : event.value?.actionStatus === 'in_progress' || event.value?.actions?.length ? '점검 기록 중' : '점검 기록 필요')
let pollTimer
let mounted = false

const loadAiGuidance = async id => {
  if (dataMode === 'mock') return
  aiLoading.value = true
  aiGuidance.value = null
  try {
    const result = await getAiGuidance(id)
    if (mounted && String(route.params.id) === String(id)) aiGuidance.value = result
  } catch {
    if (mounted) aiGuidance.value = { status: 'unavailable', answer: '추가 안내를 불러오지 못했습니다.', sources: [] }
  } finally {
    if (mounted) aiLoading.value = false
  }
}
const load = async id => {
  loading.value = true
  error.value = ''
  try {
    const [item, eventLogs, manualRows, caseRows, pastRows] = await Promise.all([
      getEvent(id), getEventLogs(id), getManuals(), getCases(), getPastActions(id).catch(() => []),
    ])
    if (!mounted) return
    event.value = item
    logs.value = eventLogs
    manuals.value = manualRows
    cases.value = caseRows
    pastActions.value = pastRows
    const saved = dataMode === 'api' ? item?.actions?.[0] : getLocalResponse(id)
    checked.value = saved?.checklist || saved?.checked || []
    action.value = saved?.actionText || saved?.action || ''
    completeAction.value = Boolean(saved?.resolved || item?.status === 'resolved')
  } catch {
    error.value = '장애 정보를 불러오지 못했습니다.'
  } finally {
    if (mounted) loading.value = false
  }
}
const refresh = async () => {
  try {
    const [item, eventLogs] = await Promise.all([getEvent(route.params.id), getEventLogs(route.params.id)])
    if (mounted) { event.value = item; logs.value = eventLogs; error.value = '' }
  } catch {
    if (mounted) error.value = '최신 장애 정보를 가져오지 못했습니다.'
  } finally {
    if (mounted) pollTimer = setTimeout(refresh, 2000)
  }
}
const save = async () => {
  if (!action.value.trim()) { ElMessage.warning('실제로 한 조치를 적어 주세요.'); return }
  saving.value = true
  try {
    await saveEventResponse(event.value.id, {
      checked: checked.value, action: action.value.trim(), resolved: completeAction.value, savedAt: new Date().toISOString(),
    })
    ElMessage.success('조치 내용을 저장했습니다.')
  } catch {
    ElMessage.error('조치 내용을 저장하지 못했습니다.')
  } finally {
    saving.value = false
  }
}
onMounted(async () => {
  mounted = true
  await load(route.params.id)
  if (mounted) pollTimer = setTimeout(refresh, 2000)
})
onUnmounted(() => { mounted = false; clearTimeout(pollTimer) })
</script>

<template>
  <div v-loading="loading" class="page-stack response-simple">
    <div class="page-intro"><div><RouterLink to="/events" class="back-link">← 장애 목록</RouterLink><h2>장애 대응</h2></div></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <el-empty v-else-if="!event && !loading" description="장애 기록을 찾을 수 없습니다." />
    <template v-else-if="event">
      <section :class="['panel', 'response-simple__status', event.recoveredAt ? 'is-recovered' : 'is-active']">
        <div><span class="response-simple__label">{{ event.deviceId }} · {{ formatTime(event.occurredAt) }}</span>
          <h3>{{ operatorTitle(event.type) }}</h3>
          <p>{{ guide?.description ?? '설비 상태를 직접 확인하고 담당자에게 알려주세요.' }}</p>
        </div>
        <strong>{{ event.recoveredAt ? '연결 정상화' : '확인 필요' }}</strong>
      </section>

      <div class="response-simple__main">
        <section class="panel">
          <div class="section-head"><div><h3>1. 순서대로 확인하세요</h3><p>확인한 항목을 선택하세요.</p></div><span class="section-meta">{{ checked.length }} / {{ steps.length }}</span></div>
          <ChecklistPanel v-model="checked" :steps="steps" />
        </section>
        <section class="panel">
          <div class="section-head"><div><h3>2. 조치 내용을 남기세요</h3><p>{{ actionStatusLabel }}</p></div></div>
          <el-input v-model="action" type="textarea" :rows="4" maxlength="1000" show-word-limit
            placeholder="확인한 내용과 실제로 한 조치를 적어 주세요" aria-label="조치 내용" />
          <el-checkbox v-model="completeAction" :disabled="event.status === 'resolved'">점검을 마쳤습니다</el-checkbox>
          <div class="form-actions"><el-button type="primary" :loading="saving" @click="save">조치 내용 저장</el-button></div>
        </section>
      </div>

      <details class="panel response-simple__more">
        <summary>기술 담당자용 상세 정보</summary>
        <div class="response-simple__technical">
          <div>
            <h3>장애 기록</h3>
            <p>장애 번호 {{ event.id }} · 지속 시간 {{ formatDuration(event.durationSeconds) }} · 복구 시각 {{ formatTime(event.recoveredAt) }}</p>
            <p>{{ event.summary }}</p>
            <h3>통신 로그</h3>
            <div v-if="logs.length" class="log-list scroll-region"><div v-for="log in logs" :key="`${log.time}-${log.message}`" class="log-row"><time>{{ formatTime(log.time) }}</time><span>{{ log.level }} · {{ log.message }}</span></div></div>
            <p v-else>연결된 로그가 없습니다.</p>
            <h3>원본 매뉴얼</h3>
            <div v-for="manual in relatedManuals" :key="manual.id"><strong>{{ manual.title }}</strong><ol><li v-for="step in manual.steps" :key="step">{{ step }}</li></ol></div>
          </div>
          <div>
            <h3>이전 조치 기록</h3>
            <div v-for="item in pastActions" :key="item.id" class="knowledge-mini"><strong>{{ item.action }}</strong><small>{{ formatTime(item.time) }}</small></div>
            <p v-if="!pastActions.length">아직 기록이 없습니다.</p>
            <h3>실습용 조치 사례</h3>
            <div v-for="item in relatedCases" :key="item.id" class="knowledge-mini"><strong>{{ item.title }}</strong><p>{{ item.action }}</p></div>
            <div class="response-simple__ai"><h3>AI 참고 안내</h3>
              <el-button v-if="dataMode === 'api'" :loading="aiLoading" @click="loadAiGuidance(event.id)">안내 생성</el-button>
              <p v-if="dataMode === 'mock'">실습 모드에서는 AI 안내를 생성하지 않습니다.</p>
              <div v-else-if="aiGuidance" class="ai-answer scroll-region" v-html="renderedAiAnswer"></div>
              <p v-else>필요할 때 안내를 생성해 확인하세요. 원인 확정은 담당자가 합니다.</p>
            </div>
          </div>
        </div>
      </details>
    </template>
  </div>
</template>
