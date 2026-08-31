<script setup lang="ts">
import { computed } from 'vue'

/**
 * 角色信息栏（M7 视觉优化：跑团常驻信息区块之一）
 * 常驻显示我的角色关键数值：HP/SAN 现值、派生值、线索数、物品数。
 */
const props = defineProps<{
  character: Record<string, unknown> | null
}>()

const char = computed(() => props.character ?? {})
const state = computed<Record<string, unknown>>(
  () => (char.value.state ?? {}) as Record<string, unknown>,
)
const derived = computed<Record<string, unknown>>(
  () => (char.value.derived ?? {}) as Record<string, unknown>,
)

const hp = computed(() => {
  const s = state.value
  return `${s.hp ?? derived.value.HP ?? '—'} / ${s.max_hp ?? derived.value.HP ?? '—'}`
})
const san = computed(() => {
  const s = state.value
  return `${s.san ?? derived.value.SAN ?? '—'} / ${s.max_san ?? derived.value.SAN ?? '—'}`
})

const statItems = computed(() => {
  const d = derived.value
  const arr: { k: string; v: string }[] = []
  if (d.MP) arr.push({ k: 'MP', v: String(d.MP) })
  if (d.MOV) arr.push({ k: 'MOV', v: String(d.MOV) })
  if (d.DB) arr.push({ k: 'DB', v: String(d.DB) })
  return arr
})

const clueCount = computed(() => {
  const c = state.value.clues
  return Array.isArray(c) ? c.length : 0
})
const itemCount = computed(() => {
  const inv = char.value.inventory
  return Array.isArray(inv) ? inv.length : 0
})
</script>

<template>
  <n-card title="我的角色" size="small" class="char-bar">
    <n-empty v-if="!character" description="尚未建卡" size="small" />
    <template v-else>
      <div class="char-name">{{ char.name }}</div>
      <div class="char-stats">
        <div class="stat">
          <span class="stat-label">HP</span>
          <span class="stat-value ok">{{ hp }}</span>
        </div>
        <div class="stat">
          <span class="stat-label">SAN</span>
          <span class="stat-value warn">{{ san }}</span>
        </div>
        <template v-for="s in statItems" :key="s.k">
          <div class="stat">
            <span class="stat-label">{{ s.k }}</span>
            <span class="stat-value">{{ s.v }}</span>
          </div>
        </template>
      </div>
      <div class="char-tags">
        <n-tag size="small" type="warning" :bordered="false">线索 {{ clueCount }}</n-tag>
        <n-tag size="small" type="info" :bordered="false">物品 {{ itemCount }}</n-tag>
      </div>
    </template>
  </n-card>
</template>

<style scoped>
.char-bar {
  width: 100%;
}
.char-name {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--text);
}
.char-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  margin-bottom: 8px;
}
.stat {
  display: flex;
  flex-direction: column;
}
.stat-label {
  font-size: 11px;
  color: var(--text-3);
}
.stat-value {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}
.stat-value.ok {
  color: var(--success-color);
}
.stat-value.warn {
  color: var(--warn-color);
}
.char-tags {
  display: flex;
  gap: 6px;
}
</style>
