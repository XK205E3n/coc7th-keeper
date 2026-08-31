<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  /** 判定卡片载荷：技能检定 {player_uid, skill, skill_value, roll, result, result_cn} 或自由掷骰 {expr, rolls, total, ...} */
  payload: Record<string, unknown>
  /** 玩家名（由父组件解析 uid 后传入） */
  playerName?: string
}>()

const SUCCESS_RESULTS = new Set(['critical', 'extreme', 'hard', 'regular'])

const isSkillCheck = computed(
  () => typeof props.payload.skill === 'string' && props.payload.skill !== '',
)

const isSuccess = computed(() => {
  const result = props.payload.result
  return typeof result === 'string' && SUCCESS_RESULTS.has(result)
})

const resultCn = computed(() => {
  const v = props.payload.result_cn
  if (typeof v === 'string' && v !== '') return v
  const result = props.payload.result
  return typeof result === 'string' ? result : ''
})

const playerLabel = computed(
  () =>
    props.playerName ||
    String(props.payload.player_uid ?? props.payload.uid ?? '未知玩家'),
)

const totalText = computed(() => {
  const rolls = Array.isArray(props.payload.rolls) ? (props.payload.rolls as number[]) : []
  const k = typeof props.payload.k === 'number' ? props.payload.k : 0
  const parts = [...rolls]
  if (k !== 0) parts.push(k)
  const total = props.payload.total
  return `${parts.join(' + ')}${typeof total === 'number' ? ` = ${total}` : ''}`
})

const whyText = computed(() => {
  const why = props.payload.why
  return typeof why === 'string' && why !== '' ? why : ''
})
</script>

<template>
  <div class="dice-card">
    <div class="dice-head">
      <span class="dice-player">{{ playerLabel }}</span>
      <n-tag v-if="resultCn" size="small" :type="isSuccess ? 'success' : 'error'" :bordered="false">
        {{ resultCn }}
      </n-tag>
    </div>

    <template v-if="isSkillCheck">
      <div class="dice-row">
        <span class="dice-label">技能</span>
        <b>{{ payload.skill }}</b>
      </div>
      <div class="dice-row">
        <span class="dice-label">目标值</span>
        <b>{{ payload.skill_value }}</b>
      </div>
      <div class="dice-row">
        <span class="dice-label">掷骰</span>
        <b class="dice-roll">{{ payload.roll }}</b>
      </div>
    </template>
    <template v-else>
      <div class="dice-row">
        <span class="dice-label">表达式</span>
        <b>{{ payload.expr }}</b>
      </div>
      <div class="dice-row">
        <span class="dice-label">结果</span>
        <b class="dice-roll">{{ totalText }}</b>
      </div>
    </template>

    <div v-if="whyText" class="dice-why">{{ whyText }}</div>
  </div>
</template>

<style scoped>
.dice-card {
  border: 1px solid var(--border, #e5e4e7);
  border-radius: 8px;
  padding: 8px 12px;
  background: var(--card-color, #fff);
}

.dice-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.dice-player {
  font-weight: 600;
  font-size: 13px;
}

.dice-row {
  display: flex;
  gap: 8px;
  align-items: baseline;
  font-size: 13px;
  line-height: 1.6;
}

.dice-label {
  color: var(--text-3, #888);
  min-width: 3em;
}

.dice-roll {
  font-size: 15px;
}

.dice-why {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-3, #888);
}
</style>
