<script setup>
import { useRoute } from 'vue-router'
import AppSidebar from './components/AppSidebar.vue'
import AppHeader from './components/AppHeader.vue'
const route = useRoute()
</script>

<template>
  <div class="app-shell">
    <AppSidebar />
    <div class="app-main">
      <AppHeader />
      <main class="page-content"><RouterView v-slot="{ Component }"><component :is="Component" :key="route.fullPath" /></RouterView></main>
    </div>
  </div>
</template>
