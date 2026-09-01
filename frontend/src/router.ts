import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

// T-B1：meta.activeMenu 供顶栏精确高亮（App.vue isActive 使用）
const routes: RouteRecordRaw[] = [
  { path: '/', name: 'overview', meta: { activeMenu: '/' }, component: () => import('./views/Overview.vue') },
  { path: '/play/:key', name: 'play', meta: { activeMenu: '/play' }, component: () => import('./views/Play.vue') },
  { path: '/characters', name: 'characters', meta: { activeMenu: '/characters' }, component: () => import('./views/Characters.vue') },
  { path: '/content', name: 'content', meta: { activeMenu: '/content' }, component: () => import('./views/Content.vue') },
  { path: '/admin', name: 'admin', meta: { activeMenu: '/admin' }, component: () => import('./views/Admin.vue') },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
