<script setup lang="ts">
import { ref } from 'vue'
import { createDiscreteApi } from 'naive-ui'
import {
  getDevGames,
  getDevResource,
  getDevRoom,
  STORAGE_KEYS,
  type DevResource,
} from '../api/client'

const { message } = createDiscreteApi(['message'])

// ---------- 开发者监视（M5.5，只读） ----------
const devToken = ref(localStorage.getItem(STORAGE_KEYS.devToken) ?? '')
const gameKey = ref('')
const roomView = ref<Record<string, unknown> | null>(null)
const gameList = ref<unknown[]>([])
const resourceData = ref<Record<string, unknown> | null>(null)
const resourceName = ref<string>('')
const loading = ref(false)

const RESOURCES: { key: DevResource; label: string }[] = [
  { key: 'messages', label: '叙事流消息' },
  { key: 'kp_notes', label: '守密人笔记' },
  { key: 'dice_log', label: '掷骰审计' },
  { key: 'state_changes', label: '状态变动' },
  { key: 'perceptions', label: '私密感知' },
  { key: 'llm_log', label: 'LLM 调用记录' },
  { key: 'clues', label: '线索台账' },
]

function saveDevToken(): void {
  localStorage.setItem(STORAGE_KEYS.devToken, devToken.value.trim())
  message.success('已保存开发者令牌（本地存储）')
}

async function onListGames(): Promise<void> {
  loading.value = true
  try {
    const res = await getDevGames(devToken.value.trim())
    gameList.value = res.games ?? []
  } catch (e) {
    message.error(e instanceof Error ? e.message : String(e))
  } finally {
    loading.value = false
  }
}

async function onRoom(): Promise<void> {
  if (!gameKey.value.trim()) {
    message.warning('请输入游戏号')
    return
  }
  loading.value = true
  try {
    roomView.value = await getDevRoom(gameKey.value.trim(), devToken.value.trim())
  } catch (e) {
    message.error(e instanceof Error ? e.message : String(e))
  } finally {
    loading.value = false
  }
}

async function onResource(res: DevResource): Promise<void> {
  if (!gameKey.value.trim()) {
    message.warning('请输入游戏号')
    return
  }
  loading.value = true
  try {
    resourceData.value = await getDevResource(
      gameKey.value.trim(),
      res,
      devToken.value.trim(),
    )
    resourceName.value = res
  } catch (e) {
    message.error(e instanceof Error ? e.message : String(e))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="page">
    <h1>开发者监视</h1>
    <n-alert type="info" :bordered="false" class="block">
      开发者监视接口为<strong>只读</strong>：可查看对话流、守密人笔记、审计与 LLM 调用记录，不参与游戏、不修改任何状态。
    </n-alert>

    <n-card title="鉴权" size="small" class="block">
      <div class="row">
        <n-input
          v-model:value="devToken"
          type="password"
          show-password-on="click"
          placeholder="X-Dev-Token（data/config.json 的 dev_token）"
        />
        <n-button type="primary" @click="saveDevToken">保存</n-button>
        <n-button :loading="loading" @click="onListGames">列出房间</n-button>
      </div>
      <n-list v-if="gameList.length > 0" size="small" class="mt">
        <n-list-item v-for="g in gameList as { game_key: string; name: string; round: number }[]" :key="g.game_key">
          <div class="row between">
            <span>{{ g.name }}（{{ g.game_key }}）第 {{ g.round }} 轮</span>
            <n-button size="tiny" @click="gameKey = g.game_key; onRoom()">查看</n-button>
          </div>
        </n-list-item>
      </n-list>
    </n-card>

    <n-card title="房间" size="small" class="block">
      <div class="row">
        <n-input v-model:value="gameKey" placeholder="游戏号" />
        <n-button type="primary" :loading="loading" @click="onRoom">房间概览</n-button>
        <template v-for="r in RESOURCES" :key="r.key">
          <n-button size="small" :loading="loading" @click="onResource(r.key)">
            {{ r.label }}
          </n-button>
        </template>
      </div>
    </n-card>

    <n-collapse v-if="roomView" class="block">
      <n-collapse-item title="房间概览（game / players / characters）" name="room">
        <pre class="json-view">{{ JSON.stringify(roomView, null, 2) }}</pre>
      </n-collapse-item>
    </n-collapse>

    <n-card v-if="resourceData" :title="`资源：${resourceName}`" size="small">
      <pre class="json-view">{{ JSON.stringify(resourceData, null, 2) }}</pre>
    </n-card>
  </section>
</template>

<style scoped>
.block {
  margin-bottom: 14px;
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.between {
  justify-content: space-between;
  width: 100%;
}
.mt {
  margin-top: 10px;
}
.json-view {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 420px;
  overflow: auto;
}
</style>
