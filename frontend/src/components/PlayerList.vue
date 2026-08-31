<script setup lang="ts">
import { ref, watch } from 'vue'
import { createDiscreteApi } from 'naive-ui'
import { kickPlayer, setAway } from '../api/client'
import type { PlayerInfo } from '../types'

const { message } = createDiscreteApi(['message'])

const props = defineProps<{
  players: PlayerInfo[]
  /** 当前玩家 uid（自己显示暂离/回归按钮） */
  myUid?: string | null
  /** 当前玩家是否房主（可移除他人） */
  isHost?: boolean
  gameKey: string
}>()

const busyUid = ref<string | null>(null)

watch(
  () => props.players,
  () => {},
)

async function onToggleAway(p: PlayerInfo): Promise<void> {
  busyUid.value = p.uid
  try {
    const target = !p.is_away
    await setAway(props.gameKey, target)
  } catch (e) {
    message.error(`操作失败：${e instanceof Error ? e.message : String(e)}`)
  } finally {
    busyUid.value = null
  }
}

async function onKick(p: PlayerInfo): Promise<void> {
  busyUid.value = p.uid
  try {
    await kickPlayer(props.gameKey, p.uid)
    message.success(`已移除玩家 ${p.name}`)
  } catch (e) {
    message.error(`移除失败：${e instanceof Error ? e.message : String(e)}`)
  } finally {
    busyUid.value = null
  }
}
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
          <span class="player-actions">
            <n-button
              v-if="p.uid === myUid"
              size="tiny"
              :loading="busyUid === p.uid"
              @click="onToggleAway(p)"
            >
              {{ p.is_away ? '回归' : '暂离' }}
            </n-button>
            <n-popconfirm
              v-if="isHost && p.uid !== myUid"
              :show-icon="false"
              @positive-click="onKick(p)"
            >
              <template #trigger>
                <n-button size="tiny" type="error" secondary :loading="busyUid === p.uid">
                  移除
                </n-button>
              </template>
              确定移除玩家 {{ p.name }} 吗？被移除后其凭证立即失效。
            </n-popconfirm>
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
  flex-shrink: 0;
}

.player-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
</style>
