<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getManuals, getCases, getKnowledgeActions } from '../services/api'
import { operatorGuidance, operatorTitle } from '../data/operatorGuidance'
import { formatTime } from '../utils/format'

const route = useRoute()
const manuals = ref([])
const cases = ref([])
const records = ref([])
const selectedType = ref(typeof route.query.type === 'string' ? route.query.type : 'all')
const tab = ref('guide')
const loading = ref(true)
const error = ref('')
const choices = [
  { value: 'all', label: '전체' },
  { value: 'message_timeout', label: '연결 끊김' },
  { value: 'response_delay', label: '응답 지연' },
  { value: 'format_error', label: '정보 오류' },
  { value: 'system', label: '화면 연결' },
]
watch(() => route.query.type, value => {
  selectedType.value = typeof value === 'string' && choices.some(choice => choice.value === value) ? value : 'all'
})
const matchType = item => selectedType.value === 'all' || item.type === selectedType.value
const visibleManuals = computed(() => manuals.value.filter(matchType))
const visibleCases = computed(() => cases.value.filter(matchType))
const visibleRecords = computed(() => records.value.filter(matchType))

onMounted(async () => {
  try {
    ;[manuals.value, cases.value, records.value] = await Promise.all([
      getManuals(), getCases(), getKnowledgeActions().catch(() => []),
    ])
  } catch {
    error.value = '점검 안내를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-loading="loading" class="page-stack operator-knowledge">
    <div class="page-intro"><div><h2>장애가 생겼을 때</h2><p>화면에 표시된 문제를 고르고 순서대로 확인하세요.</p></div></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <template v-else>
      <div class="operator-filter" aria-label="문제 종류 선택">
        <button v-for="choice in choices" :key="choice.value" type="button"
          :class="{ active: selectedType === choice.value }"
          :aria-pressed="selectedType === choice.value"
          @click="selectedType = choice.value">{{ choice.label }}</button>
      </div>
      <el-tabs v-model="tab" class="operator-knowledge-tabs">
        <el-tab-pane label="지금 할 일" name="guide">
          <div v-if="visibleManuals.length" class="operator-guide-list">
            <article v-for="manual in visibleManuals" :key="manual.id" class="panel operator-guide">
              <h3>{{ operatorGuidance[manual.type]?.title ?? '설비 상태를 확인해 주세요' }}</h3>
              <p>{{ operatorGuidance[manual.type]?.description ?? '담당자에게 문제 발생 시각과 설비 이름을 알려주세요.' }}</p>
              <ol>
                <li v-for="step in operatorGuidance[manual.type]?.steps ?? []" :key="step">{{ step }}</li>
              </ol>
              <details class="operator-technical">
                <summary>기술 담당자용 점검 내용</summary>
                <h4>{{ manual.title }}</h4>
                <ol><li v-for="step in manual.steps" :key="step">{{ step }}</li></ol>
              </details>
            </article>
          </div>
          <el-empty v-else description="해당하는 점검 안내가 없습니다." />
        </el-tab-pane>
        <el-tab-pane label="이전 조치" name="records">
          <p class="operator-note">이 시스템에 실제로 저장한 조치 기록입니다. 자세한 내용은 담당자가 확인하세요.</p>
          <div v-if="visibleRecords.length" class="operator-guide-list">
            <article v-for="item in visibleRecords" :key="item.id" class="panel operator-guide operator-guide--history">
              <h3>{{ operatorTitle(item.type) }}</h3>
              <p>{{ formatTime(item.time) }}에 조치 기록이 남았습니다.</p>
              <details class="operator-technical"><summary>조치 내용 보기</summary><p>{{ item.action }}</p><RouterLink :to="`/events/${item.eventId}`">장애 상세 보기 →</RouterLink></details>
            </article>
          </div>
          <el-empty v-else description="저장된 조치 기록이 없습니다." />
        </el-tab-pane>
        <el-tab-pane label="예시 사례" name="cases">
          <p class="operator-note">아래 내용은 실습용 예시입니다. 실제 현장 조치 기록이 아닙니다.</p>
          <div v-if="visibleCases.length" class="operator-guide-list">
            <article v-for="item in visibleCases" :key="item.id" class="panel operator-guide operator-guide--history">
              <h3>{{ operatorTitle(item.type) }}</h3>
              <p>비슷한 문제가 발생했을 때의 예시입니다.</p>
              <details class="operator-technical"><summary>예시 조치 내용 보기</summary><h4>{{ item.title }}</h4><p>{{ item.action }}</p></details>
            </article>
          </div>
          <el-empty v-else description="해당하는 예시가 없습니다." />
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>
