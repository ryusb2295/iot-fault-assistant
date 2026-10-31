import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', name: 'dashboard', component: () => import('../views/DashboardView.vue'), meta: { title: '대시보드' } },
    { path: '/devices', name: 'devices', component: () => import('../views/DevicesView.vue'), meta: { title: '설비 모니터링' } },
    { path: '/events', name: 'events', component: () => import('../views/EventsView.vue'), meta: { title: '장애 이력' } },
    { path: '/response', name: 'response', component: () => import('../views/ResponseRedirectView.vue'), meta: { title: '장애 대응' } },
    { path: '/events/:id', name: 'event-detail', component: () => import('../views/EventDetailView.vue'), meta: { title: '장애 대응' } },
    { path: '/knowledge', name: 'knowledge', component: () => import('../views/KnowledgeView.vue'), meta: { title: '매뉴얼 및 조치 사례' } },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

export default router
