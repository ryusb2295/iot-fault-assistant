<script setup>
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'
import { formatTime, formatElapsed } from '../utils/format'

const props = defineProps({ device: { type: Object, required: true }, now: { type: Number, default: () => Date.now() } })
const elapsed = computed(() => formatElapsed(props.device.lastReceivedAt, props.now))
</script>
<template>
  <div class="device-card">
    <div class="device-head"><div><div class="device-id">{{ device.id }}</div><div class="muted">{{ device.name }}</div></div><StatusBadge :kind="device.status === 'normal' ? 'success' : device.status === 'unknown' ? 'info' : 'danger'" :label="device.status === 'normal' ? '통신 정상' : device.status === 'unknown' ? '수신 대기' : '통신 장애'" /></div>
    <div class="device-metrics"><div><small>마지막 메시지 수신</small><strong>{{ formatTime(device.lastReceivedAt) }}</strong></div><div><small>수신 이후 경과</small><strong>{{ elapsed }}</strong></div><div><small>설정 수신 주기</small><strong>{{ device.intervalSeconds }}초</strong></div></div>
    <div class="device-foot"><span class="muted">MQTT Topic</span><code>{{ device.topic }}</code></div>
  </div>
</template>
