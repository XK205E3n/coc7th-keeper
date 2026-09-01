<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { darkTheme, type GlobalThemeOverrides } from 'naive-ui'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const auth = useAuthStore()

/**
 * 顶栏导航。「游玩」跳到当前凭证所属的房间（无游戏时回总览）。
 * activeKey：高亮判定所用的键（「游玩」的跳转目标在无游戏时是 /，
 * 但高亮应只在游戏页生效，故与 to 分离）。
 */
const navItems = computed(() => [
  { label: '总览', to: '/', activeKey: '/' },
  { label: '游玩', to: auth.gameKey ? `/play/${auth.gameKey}` : '/', activeKey: '/play' },
  { label: '角色', to: '/characters', activeKey: '/characters' },
  { label: '内容', to: '/content', activeKey: '/content' },
  { label: '管理', to: '/admin', activeKey: '/admin' },
])

/** T-B1：按路由 meta.activeMenu（缺省用 path）精确匹配，避免祖先路径双高亮 */
function isActive(item: { to: string; activeKey: string }): boolean {
  const activeKey = (route.meta.activeMenu as string | undefined) ?? route.path
  return (item.activeKey ?? item.to) === activeKey
}

/** 暗色主题定制（M7 视觉优化：整体偏暗，暗紫主色保证对比） */
const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#a78bfa',
    primaryColorHover: '#c4b5fd',
    primaryColorPressed: '#8b5cf6',
    primaryColorSuppl: '#7c3aed',
    bodyColor: '#121016',
    cardColor: '#1a1720',
    modalColor: '#1f1b27',
    popoverColor: '#1f1b27',
    tableColor: '#1a1720',
    inputColor: '#141219',
    textColorBase: '#e7e3ee',
    textColor1: '#efeaf6',
    textColor2: '#d8d2e2',
    textColor3: '#9d94ad',
    borderColor: '#332d3e',
    dividerColor: '#2a2533',
    borderRadius: '8px',
  },
}
</script>

<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-message-provider placement="top-right">
      <n-dialog-provider>
        <div class="app-shell">
          <header class="app-header">
            <span class="app-title">🕯 CoC 跑团平台</span>
            <nav class="app-nav">
              <RouterLink
                v-for="item in navItems"
                :key="item.activeKey"
                :to="item.to"
                class="app-nav-link"
                :class="{ 'is-active': isActive(item) }"
              >
                {{ item.label }}
              </RouterLink>
            </nav>
          </header>
          <main class="app-main">
            <RouterView />
          </main>
          <footer class="app-footer">
            <span>AI 守密人 · CoC7th</span>
          </footer>
        </div>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
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
  background: linear-gradient(180deg, #1c1923 0%, #16131b 100%);
  border-bottom: 1px solid #332d3e;
  position: sticky;
  top: 0;
  z-index: 10;
}

.app-title {
  font-weight: 700;
  font-size: 16px;
  letter-spacing: 0.5px;
  color: #e9e2f5;
}

.app-nav {
  display: flex;
  gap: 14px;
}

.app-nav-link {
  color: #b3aac4;
  text-decoration: none;
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 14px;
  transition: color 0.15s, background 0.15s;
}

.app-nav-link:hover {
  color: #e9e2f5;
  background: rgba(167, 139, 250, 0.12);
}

.app-nav-link.is-active {
  font-weight: 600;
  color: #c4b5fd;
  background: rgba(167, 139, 250, 0.16);
}

.app-main {
  flex: 1;
  padding: 22px 24px;
}

.app-footer {
  padding: 10px 24px;
  font-size: 12px;
  color: #6b6378;
  border-top: 1px solid #241f2c;
  text-align: center;
}

/* T-A1 移动端（≤640px）：顶栏换行不溢出、主区边距收紧 */
@media (max-width: 640px) {
  .app-header {
    flex-wrap: wrap;
    gap: 8px 16px;
    padding: 10px 12px;
  }

  .app-title {
    font-size: 14px;
  }

  .app-nav {
    gap: 6px;
    flex-wrap: wrap;
    width: 100%;
  }

  .app-nav-link {
    padding: 4px 10px;
    font-size: 13px;
  }

  .app-main {
    padding: 14px 12px;
  }

  .app-footer {
    padding: 8px 12px;
  }
}

/* T-A1 平板（641–1024px）：边距略收 */
@media (min-width: 641px) and (max-width: 1024px) {
  .app-header {
    padding: 12px 16px;
  }

  .app-main {
    padding: 18px 16px;
  }
}

</style>
