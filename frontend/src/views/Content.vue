<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { createDiscreteApi } from 'naive-ui'
import { getModuleScenes, getModules } from '../api/client'
import EmptyState from '../components/EmptyState.vue'
import type { ModuleInfo } from '../types'

const { message } = createDiscreteApi(['message'])

const modules = ref<ModuleInfo[]>([])
const loading = ref(false)
const loadError = ref<string | null>(null)

/** 展开的模组 → 场景数（懒加载；场景名不展示——场景名可能含剧透） */
const sceneCounts = ref<Record<string, number>>({})
const loadingScenes = ref<Set<string>>(new Set())

async function reload(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const res = await getModules()
    modules.value = res.modules
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void reload()
})

async function onExpand(moduleId: string): Promise<void> {
  if (sceneCounts.value[moduleId] !== undefined) return
  loadingScenes.value = new Set(loadingScenes.value).add(moduleId)
  try {
    const res = await getModuleScenes(moduleId)
    sceneCounts.value[moduleId] = res.scene_flow.length || res.scenes.length
  } catch (e) {
    message.error(`场景加载失败：${e instanceof Error ? e.message : String(e)}`)
  } finally {
    const next = new Set(loadingScenes.value)
    next.delete(moduleId)
    loadingScenes.value = next
  }
}
</script>

<template>
  <section class="page">
    <div class="page-head">
      <h1>内容</h1>
      <span class="sub">模组库</span>
    </div>

    <n-alert v-if="loadError" type="error" class="block">{{ loadError }}</n-alert>

    <n-spin :show="loading">
      <EmptyState v-if="!loading && modules.length === 0" description="暂无模组" actionLabel="重新加载" @action="reload" />
      <n-collapse v-else accordion @item-header-click="(info: { name: string }) => onExpand(info.name)">
        <n-collapse-item v-for="m in modules" :key="m.id" :name="m.id">
          <template #header>
            <div class="module-head">
              <span class="module-cn">{{ m.cn }}</span>
              <span class="module-name">{{ m.name }}</span>
              <span class="module-meta">{{ m.players }} · {{ m.duration }}</span>
            </div>
          </template>
          <div class="module-body">
            <!-- 只展示无剧透简介（public_summary）；summary 为 KP 视角，绝不给玩家看 -->
            <p v-if="m.public_summary" class="module-summary">{{ m.public_summary }}</p>
            <p v-else class="module-summary module-summary-empty">
              剧情简介对玩家保密——入团后由守密人在游戏中逐步揭晓。
            </p>
            <n-spin :show="loadingScenes.has(m.id)" size="small">
              <template v-if="sceneCounts[m.id] !== undefined">
                <p class="module-scenes">场景数：{{ sceneCounts[m.id] }}</p>
              </template>
              <p v-else class="module-scenes">点击展开查看场景…</p>
            </n-spin>
          </div>
        </n-collapse-item>
      </n-collapse>
    </n-spin>
  </section>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 16px;
}

.page-head h1 {
  margin: 0;
  font-size: 22px;
}

.sub {
  font-size: 13px;
  color: var(--text-3, #888);
}

.block {
  margin-bottom: 14px;
}

.module-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.module-cn {
  font-weight: 600;
}

.module-name {
  color: var(--text-3, #888);
  font-size: 13px;
}

.module-meta {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-3, #888);
}

.module-summary {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-2, #666);
}

.module-summary-empty {
  color: var(--text-3, #888);
  font-style: italic;
}

.module-scenes {
  font-size: 13px;
  color: var(--text, #333);
}

/* T-A1 mobile ≤640px */
@media (max-width: 640px) {
  .page-head {
    flex-wrap: wrap;
  }

  .module-meta {
    margin-left: 0;
  }

  .module-head {
    align-items: flex-start;
  }

  .module-cn,
  .module-name,
  .module-summary,
  .module-scenes {
    overflow-wrap: anywhere;
  }
}
</style>
