<script setup lang="ts">
const navItems = [
  { label: '总览', to: '/' },
  { label: '游玩', to: '/play/demo' },
  { label: '角色', to: '/characters' },
  { label: '内容', to: '/content' },
  { label: '管理', to: '/admin' },
] as const
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <span class="app-title">CoC 跑团平台</span>
      <nav class="app-nav">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="app-nav-link">
          {{ item.label }}
        </RouterLink>
      </nav>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border, #e5e4e7);
}

.app-title {
  font-weight: 700;
  font-size: 16px;
  color: var(--text-h, #08060d);
}

.app-nav {
  display: flex;
  gap: 16px;
}

.app-nav-link {
  color: var(--text, #444);
  text-decoration: none;
  padding: 4px 8px;
  border-radius: 6px;
}

.app-nav-link:hover {
  background: rgba(128, 128, 128, 0.12);
}

.app-nav-link.router-link-active {
  font-weight: 600;
  color: var(--accent, #7c3aed);
}

.app-main {
  flex: 1;
  padding: 24px;
}
</style>
