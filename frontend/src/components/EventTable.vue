<script setup>
import StatusBadge from './StatusBadge.vue'
import { eventTypes } from '../data/mockData'
import { formatTime, formatDuration } from '../utils/format'
defineProps({ rows: { type: Array, default: () => [] }, loading: Boolean })
const actionLabel = (row) => row.actionStatus === 'completed' || row.status === 'resolved' ? '조치 완료' : row.actionStatus === 'in_progress' ? '점검 중' : '미조치'
const actionKind = (row) => row.actionStatus === 'completed' || row.status === 'resolved' ? 'success' : row.actionStatus === 'in_progress' ? 'info' : 'warning'
</script>
<template>
  <div class="table-scroll"><el-table v-loading="loading" :data="rows" class="event-table" empty-text="조건에 맞는 장애 이력이 없습니다" table-layout="auto">
    <el-table-column prop="id" label="장애 ID" min-width="145" />
    <el-table-column prop="deviceId" label="장치 ID" width="90" />
    <el-table-column label="장애 유형" min-width="145"><template #default="scope"><StatusBadge :kind="scope.row.type === 'response_delay' ? 'warning' : 'danger'" :label="eventTypes[scope.row.type] || scope.row.type" /></template></el-table-column>
    <el-table-column label="발생 시각" min-width="155"><template #default="scope">{{ formatTime(scope.row.occurredAt) }}</template></el-table-column>
    <el-table-column label="복구 시각" min-width="155"><template #default="scope">{{ formatTime(scope.row.recoveredAt) }}</template></el-table-column>
    <el-table-column label="지속 시간" width="90"><template #default="scope">{{ formatDuration(scope.row.durationSeconds) }}</template></el-table-column>
    <el-table-column label="복구 상태" width="100"><template #default="scope"><StatusBadge :kind="scope.row.recoveredAt ? 'success' : 'danger'" :label="scope.row.recoveredAt ? '복구됨' : '미복구'" /></template></el-table-column>
    <el-table-column label="조치 상태" width="100"><template #default="scope"><StatusBadge :kind="actionKind(scope.row)" :label="actionLabel(scope.row)" /></template></el-table-column>
    <el-table-column label="상세 보기" width="95" fixed="right"><template #default="scope"><RouterLink class="text-link" :to="`/events/${scope.row.id}`">상세 보기 →</RouterLink></template></el-table-column>
  </el-table></div>
</template>
