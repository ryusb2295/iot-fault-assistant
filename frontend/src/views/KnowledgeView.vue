<script setup>
import { ref, computed, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { getManuals, getCases } from '../services/api'
import { eventTypes } from '../data/mockData'
import StatusBadge from '../components/StatusBadge.vue'
const manuals = ref([])
const cases = ref([])
const query = ref('')
const tab = ref('manuals')
const loading = ref(true)
const error = ref('')
const visibleManuals = computed(() => manuals.value.filter((item) => `${item.title} ${eventTypes[item.type]} ${item.steps.join(' ')}`.toLowerCase().includes(query.value.trim().toLowerCase())))
const visibleCases = computed(() => cases.value.filter((item) => `${item.title} ${eventTypes[item.type]} ${item.action}`.toLowerCase().includes(query.value.trim().toLowerCase())))
onMounted(async () => { try { [manuals.value, cases.value] = await Promise.all([getManuals(), getCases()]) } catch { error.value = '문서 데이터를 불러오지 못했습니다.' } finally { loading.value = false } })
</script>
<template>
  <div v-loading="loading" class="page-stack"><div class="page-intro"><div><span class="eyebrow">KNOWLEDGE BASE</span><h2>매뉴얼 및 조치 사례</h2><p>점검 매뉴얼은 로컬 문서 파일에서 제공하며 조치 사례는 실습용 예시입니다.</p></div></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <section v-else class="panel"><div class="section-head"><div><h3>지식 자료 검색</h3><p>문서 제목, 장애 유형, 점검·조치 내용으로 검색</p></div><span class="section-meta">매뉴얼: 로컬 문서 · 사례: 예시</span></div><el-input v-model="query" placeholder="검색어를 입력하세요" clearable :prefix-icon="Search" class="knowledge-search" aria-label="매뉴얼 및 사례 검색" />
      <el-tabs v-model="tab" class="knowledge-tabs"><el-tab-pane :label="`점검 매뉴얼 (${visibleManuals.length})`" name="manuals"><div v-if="visibleManuals.length" class="knowledge-list"><article v-for="manual in visibleManuals" :key="manual.id" class="knowledge-card"><div class="knowledge-top"><div><small>{{ manual.id }} · 수정 {{ manual.updatedAt }}</small><h4>{{ manual.title }}</h4></div><StatusBadge kind="info" :label="eventTypes[manual.type]" /></div><ol><li v-for="step in manual.steps" :key="step">{{ step }}</li></ol></article></div><el-empty v-else description="검색 결과가 없습니다" /></el-tab-pane>
      <el-tab-pane :label="`과거 조치 사례 (${visibleCases.length})`" name="cases"><div v-if="visibleCases.length" class="knowledge-list"><article v-for="item in visibleCases" :key="item.id" class="knowledge-card"><div class="knowledge-top"><div><small>{{ item.id }} · {{ item.date }}</small><h4>{{ item.title }}</h4></div><StatusBadge kind="info" :label="eventTypes[item.type]" /></div><p>{{ item.action }}</p></article></div><el-empty v-else description="검색 결과가 없습니다" /></el-tab-pane></el-tabs>
    </section>
  </div>
</template>
