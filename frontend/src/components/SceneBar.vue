<script setup lang="ts">
/**
 * 场景栏（M7 视觉优化：跑团常驻信息区块之一）
 * 展示当前场景名/地点/入场白 + 回合与阶段，保持常驻可见。
 * brief 为玩家可见的场景入场白（scenes.json intro）——KP 视角 summary 不进此组件。
 */
defineProps<{
  name: string
  location?: string
  brief?: string
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
    <div v-if="brief" class="scene-brief">{{ brief }}</div>
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
.scene-brief {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-2);
  white-space: pre-wrap;
}
</style>
