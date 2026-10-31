<script setup>
defineProps({ steps: { type: Array, default: () => [] }, modelValue: { type: Array, default: () => [] } })
defineEmits(['update:modelValue'])
</script>
<template><div v-if="steps.length" class="checklist"><el-checkbox-group :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)"><el-checkbox v-for="(step, index) in steps" :key="step" :value="index" class="checklist-item">{{ step }}</el-checkbox></el-checkbox-group></div><el-empty v-else description="점검 항목이 없습니다" /></template>
