<script setup lang="ts">
import type { PlayerInfo } from '../types'

defineProps<{
  players: PlayerInfo[]
}>()
</script>

<template>
  <n-card title="玩家" size="small">
    <n-empty v-if="players.length === 0" description="暂无玩家" size="small" />
    <n-list v-else>
      <n-list-item v-for="p in players" :key="p.uid">
        <div class="player-row">
          <span class="player-name">{{ p.name }}</span>
          <span class="player-tags">
            <n-tag v-if="p.is_host" size="small" type="warning" :bordered="false">房主</n-tag>
            <n-tag v-if="p.has_submitted" size="small" type="success" :bordered="false">已提交</n-tag>
            <n-tag v-if="p.is_away" size="small" type="error" :bordered="false">暂离</n-tag>
          </span>
        </div>
      </n-list-item>
    </n-list>
  </n-card>
</template>

<style scoped>
.player-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
}

.player-name {
  font-size: 13px;
  font-weight: 500;
}

.player-tags {
  display: flex;
  gap: 4px;
}
</style>
