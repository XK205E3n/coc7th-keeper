<script setup lang="ts">
import { computed } from 'vue'
import { useGameStore } from '../stores/game'

const props = defineProps<{
  /** 状态变动载荷：{type, player_uid, ...}，type ∈ hp/san/item/clue/scene */
  payload: Record<string, unknown>
}>()

const gameStore = useGameStore()

const TYPE_LABELS: Record<string, string> = {
  hp: '体力',
  san: '理智',
  item: '物品',
  clue: '线索',
  scene: '场景',
}

const typeLabel = computed(() => {
  const t = props.payload.type
  return typeof t === 'string' ? (TYPE_LABELS[t] ?? t) : '状态'
})

const playerName = computed(() => {
  const uid = props.payload.player_uid
  if (typeof uid !== 'string' || uid === '') return ''
  return gameStore.players.find((p) => p.uid === uid)?.name ?? ''
})

const description = computed(() => {
  const p = props.payload
  switch (p.type) {
    case 'hp': {
      const delta = typeof p.delta === 'number' ? p.delta : 0
      const sign = delta >= 0 ? '+' : ''
      const wound = p.major_wound ? '（重伤）' : ''
      return `HP ${sign}${delta} → ${String(p.hp ?? '?')}/${String(p.max_hp ?? '?')}${wound}`
    }
    case 'san': {
      const delta = typeof p.delta === 'number' ? p.delta : 0
      const sign = delta >= 0 ? '+' : ''
      const insane = p.permanent_insanity ? '（永久疯狂）' : ''
      return `SAN ${sign}${delta} → ${String(p.san ?? '?')}/${String(p.max_san ?? '?')}${insane}`
    }
    case 'item': {
      const action = p.action === 'lose' || p.action === 'consume' ? '失去' : '获得'
      return `${action}物品：${String(p.item ?? '')}`
    }
    case 'clue':
      return `线索：${String(p.text ?? p.clue_id ?? '')}`
    case 'scene':
      return `场景切换：${String(p.name ?? p.scene_id ?? '')}`
    default:
      return JSON.stringify(p)
  }
})
</script>

<template>
  <div class="state-change">
    <n-tag size="small" :bordered="false" type="info">{{ typeLabel }}</n-tag>
    <span class="state-desc">
      <template v-if="playerName">（{{ playerName }}）</template>
      {{ description }}
    </span>
  </div>
</template>

<style scoped>
.state-change {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  line-height: 1.6;
  padding: 2px 0;
}

.state-desc {
  color: var(--text, #333);
  word-break: break-all;
}
</style>
