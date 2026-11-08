<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Odometer, Monitor, Warning, FirstAidKit, Reading, InfoFilled } from '@element-plus/icons-vue'

const route = useRoute()
const items = [
  { label: '대시보드', to: '/dashboard', icon: Odometer },
  { label: '설비 모니터링', to: '/devices', icon: Monitor },
  { label: '장애 이력', to: '/events', icon: Warning },
  { label: '장애 대응', to: '/response', icon: FirstAidKit },
  { label: '매뉴얼 및 조치 사례', to: '/knowledge', icon: Reading },
]
const activeMenu = computed(() => route.name === 'event-detail' ? '/response' : route.path)
</script>

<template>
  <aside class="sidebar">
    <RouterLink class="brand" to="/dashboard"><span class="brand-mark">FM</span><span>IoT Fault<br /><strong>Monitoring</strong></span></RouterLink>
    <div class="sidebar-caption">WORKSPACE</div>
    <nav class="sidebar-nav" aria-label="주 메뉴">
      <RouterLink v-for="item in items" :key="item.label" :to="item.to" :aria-current="activeMenu === item.to ? 'page' : undefined" :class="['nav-item', { active: activeMenu === item.to }]">
        <el-icon :size="16"><component :is="item.icon" /></el-icon><span>{{ item.label }}</span>
      </RouterLink>
    </nav>
    <div class="sidebar-bottom"><el-icon><InfoFilled /></el-icon><div><strong>시스템 정보</strong><small>Local Monitoring · v1.0</small></div></div>
  </aside>
</template>
