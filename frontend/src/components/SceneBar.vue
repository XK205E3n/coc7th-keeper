<script setup lang="ts">
/**
 * 场景栏（M7 视觉优化：跑团常驻信息区块之一）
 * 展示当前场景名/地点/摘要 + 回合与阶段，保持常驻可见。
 */
defineProps<{
  name: string
  location?: string
  summary?: string
  round: number
  phaseLabel: string
}>()
</script>

<template>
  <n-card class="scene-bar" size="small" :bordered="true">
    <div class="scene-head">
      <div class="scene-title">
        <span class="scene-name">{{ name || '—' }}</span>
        <span v-if="location" class="scene-loc">{{ location }}</span>
      </div>
      <div class="scene-meta">
        <n-tag size="small" :bordered="false">第 {{ round }} 轮</n-tag>
        <n-tag size="small" type="info" :bordered="false">{{ phaseLabel }}</n-tag>
      </div>
    </div>
    <div v-if="summary" class="scene-summary">{{ summary }}</div>
  </n-card>
</template>

<style scoped>
.scene-bar {
  border-left: 3px solid var(--accent);
  background: linear-gradient(180deg, #191620 0%, #16131b 100%);
  margin-bottom: 12px;
}
.scene-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.scene-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}
.scene-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
}
.scene-loc {
  font-size: 13px;
  color: var(--text-3);
}
.scene-meta {
  display: flex;
  gap: 6px;
}
.scene-summary {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-2);
  white-space: pre-wrap;
}
</style>
