<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getEvents } from '../services/api'

const router = useRouter()
const error = ref('')
onMounted(async () => {
  try {
    const events = await getEvents()
    const target = events.find((event) => event.status === 'open') || events[0]
    if (target) await router.replace(`/events/${target.id}`)
    else await router.replace('/events')
  } catch { error.value = '백엔드 연결 실패: 장애 목록을 불러오지 못했습니다.' }
})
</script>
<template><div class="page-stack"><el-alert v-if="error" :title="error" type="error" show-icon :closable="false" /><div v-else v-loading="true" class="panel" style="min-height: 200px">장애 대응 화면으로 이동 중...</div></div></template>
