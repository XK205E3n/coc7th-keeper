import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'overview', component: () => import('./views/Overview.vue') },
  { path: '/play/:key', name: 'play', component: () => import('./views/Play.vue') },
  { path: '/characters', name: 'characters', component: () => import('./views/Characters.vue') },
  { path: '/content', name: 'content', component: () => import('./views/Content.vue') },
  { path: '/admin', name: 'admin', component: () => import('./views/Admin.vue') },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
