<script setup>
defineProps({ kind: { type: String, default: 'info' }, label: { type: String, required: true } })
</script>
<template><span :class="['status-badge', `status-${kind}`]"><span class="status-dot"></span>{{ label }}</span></template>
