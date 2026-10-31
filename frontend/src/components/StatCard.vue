<script setup>
defineProps({ label: String, value: [String, Number], unit: { type: String, default: '건' }, note: String, tone: { type: String, default: 'blue' }, icon: Object })
</script>
<template>
  <div class="stat-card panel"><div class="stat-top"><span>{{ label }}</span><span :class="['stat-icon', `tone-${tone}`]"><el-icon :size="18"><component :is="icon" /></el-icon></span></div><div class="stat-value">{{ value }}<small>{{ unit }}</small></div><div class="stat-note">{{ note }}</div></div>
</template>
