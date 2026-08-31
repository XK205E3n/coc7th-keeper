<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createDiscreteApi } from 'naive-ui'
import { freeRoll, getGame, getModuleScenes } from '../api/client'
import { connectEvents } from '../api/sse'
import type { SseHandle } from '../api/sse'
import { useAuthStore } from '../stores/auth'
import { useGameStore } from '../stores/game'
import NarrationStream from '../components/NarrationStream.vue'
import PlayerList from '../components/PlayerList.vue'
import PerceptionPanel from '../components/PerceptionPanel.vue'
import ActionInput from '../components/ActionInput.vue'

const { message } = createDiscreteApi(['message'])

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const gameStore = useGameStore()

const gameKey = computed(() => (typeof route.params.key === 'string' ? route.params.key : ''))
const hasToken = computed(() => auth.playerToken !== null)
/** 当前凭证属于其他游戏时提示（最近游戏列表直进场景） */
const tokenMismatch = computed(
  () => auth.gameKey !== null && auth.gameKey !== gameKey.value,
)

// ---------- 自由掷骰 ----------
const rollExpr = ref('')
const rollResult = ref<string | null>(null)
const rollError = ref<string | null>(null)
const rolling = ref(false)

// ---------- 场景名映射（module scenes id → name） ----------
const sceneNames = ref<Record<string, string>>({})
const currentSceneName = computed(() => {
  const id = gameStore.game?.current_scene
  if (!id) return '—'
  return sceneNames.value[id] ?? id
})

const PHASE_LABELS: Record<string, string> = {
  lobby: '大厅',
  collecting: '收集行动',
  adjudicating: '判定中',
  narrating: '叙事中',
}
const phaseLabel = computed(() => {
  const p = gameStore.phase
  return p !== null ? (PHASE_LABELS[p] ?? p) : '—'
})

let sseHandle: SseHandle | null = null
/** 初始化代际号：路由快速切换时丢弃过期初始化，避免旧房间数据串台 */
let initSeq = 0

/** 房间加载失败（不存在/404/网络错误）时给出明确错误页，不再卡"加载中" */
const loadFailed = ref(false)
const failMessage = ref('')

async function initGame(): Promise<void> {
  const seq = ++initSeq
  sseHandle?.close()
  sseHandle = null
  // 切换游戏时清掉上一个房间的残留状态
  gameStore.reset()
  rollResult.value = null
  rollError.value = null
  sceneNames.value = {}
  loadFailed.value = false
  failMessage.value = ''
  if (!gameKey.value || !hasToken.value) return
  // 凭证属于其他游戏（如顶栏"游玩"曾指向 /play/demo）：自动跳回凭证所属房间
  if (auth.gameKey && auth.gameKey !== gameKey.value) {
    router.replace(`/play/${auth.gameKey}`)
    return
  }
  try {
    const view = await getGame(gameKey.value)
    if (seq !== initSeq) return
    gameStore.setGame(view.game)
    await gameStore.loadMessages(gameKey.value)
    if (view.game.module_id) {
      try {
        const scenes = await getModuleScenes(view.game.module_id)
        const map: Record<string, string> = {}
        for (const s of scenes.scenes) map[s.id] = s.name
        sceneNames.value = map
      } catch {
        // 场景名映射失败不阻塞游玩
      }
    }
    const handle = connectEvents(gameKey.value, {
      playerToken: auth.playerToken ?? undefined,
      onEvent: gameStore.onEvent,
      onReconnect: () => {
        getGame(gameKey.value)
          .then((v) => gameStore.setGame(v.game))
          .catch(() => {})
        gameStore.loadMessages(gameKey.value).catch(() => {})
      },
    })
    if (seq !== initSeq) {
      handle.close()
      return
    }
    sseHandle = handle
  } catch (e) {
    if (seq !== initSeq) return
    loadFailed.value = true
    failMessage.value = e instanceof Error ? e.message : String(e)
  }
}

onMounted(initGame)

// /play/A → /play/B 时组件复用不重挂载，监听 key 变化重新初始化
watch(gameKey, () => {
  initGame()
})

onUnmounted(() => {
  initSeq += 1
  sseHandle?.close()
  sseHandle = null
})

async function onFreeRoll(): Promise<void> {
  const expr = rollExpr.value.trim()
  if (!expr) {
    message.warning('请输入骰子表达式，如 1d100 或 2d6+3')
    return
  }
  rolling.value = true
  rollError.value = null
  try {
    const res = await freeRoll(gameKey.value, expr)
    const r = res.result
    const rolls = Array.isArray(r.rolls) ? r.rolls : []
    const k = typeof r.k === 'number' ? r.k : 0
    const parts = [...rolls]
    if (k !== 0) parts.push(k)
    const detail = parts.join(' + ')
    const by = typeof r.by === 'string' && r.by !== '' ? `（${r.by}${r.why ? `：${r.why}` : ''}）` : ''
    rollResult.value = `${r.expr} = ${r.total}${detail ? `　[${detail}]` : ''}${by}`
  } catch (e) {
    rollError.value = e instanceof Error ? e.message : String(e)
    rollResult.value = null
  } finally {
    rolling.value = false
  }
}
</script>

<template>
  <section class="page">
    <!-- 未登录 -->
    <n-result
      v-if="!hasToken"
      status="info"
      title="尚未加入游戏"
      description="请先在总览页创建或加入游戏"
    >
      <template #footer>
        <n-button type="primary" @click="router.push('/')">前往总览</n-button>
      </template>
    </n-result>

    <n-result
      v-else-if="loadFailed"
      status="error"
      title="无法进入该房间"
      :description="failMessage || '房间不存在或网络错误'"
    >
      <template #footer>
        <n-button type="primary" @click="router.push('/')">返回总览</n-button>
      </template>
    </n-result>

    <template v-else>
      <n-alert v-if="tokenMismatch" type="warning" class="block">
        当前登录凭证属于游戏 {{ auth.gameKey }}，与当前房间不匹配；消息与行动可能失败，请返回
        <RouterLink to="/">总览</RouterLink>
        重新加入。
      </n-alert>

      <!-- 顶部：游戏名 + 回合 + 阶段 + 场景 -->
      <div class="play-top">
        <h2 class="play-title">{{ gameStore.game?.name ?? '加载中…' }}</h2>
        <n-tag size="small" :bordered="false">第 {{ gameStore.round }} 轮</n-tag>
        <n-tag size="small" type="info" :bordered="false">{{ phaseLabel }}</n-tag>
        <n-tag size="small" type="warning" :bordered="false">场景：{{ currentSceneName }}</n-tag>
      </div>

      <div class="play-layout">
        <!-- 主区：叙事流 -->
        <div class="play-main">
          <NarrationStream :messages="gameStore.messages" />
        </div>

        <!-- 右栏 -->
        <aside class="play-side">
          <PlayerList :players="gameStore.players" />
          <PerceptionPanel :perceptions="gameStore.perceptions" />
          <ActionInput
            :submitted="gameStore.actionsSubmitted.submitted"
            :round="gameStore.round"
            :game-key="gameKey"
          />

          <!-- 自由掷骰 -->
          <n-card title="自由掷骰" size="small">
            <div class="roll-row">
              <n-input
                v-model:value="rollExpr"
                placeholder="如 1d100 / 2d6+3"
                :disabled="rolling"
                @keyup.enter="onFreeRoll"
              />
              <n-button type="primary" :loading="rolling" :disabled="rolling" @click="onFreeRoll">
                掷骰
              </n-button>
            </div>
            <n-alert v-if="rollResult" type="success" class="roll-result" :bordered="false">
              {{ rollResult }}
            </n-alert>
            <n-alert v-if="rollError" type="error" class="roll-result" :bordered="false">
              {{ rollError }}
            </n-alert>
          </n-card>
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.block {
  margin-bottom: 14px;
}

.play-top {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.play-title {
  margin: 0;
  font-size: 20px;
}

.play-layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.play-main {
  flex: 1;
  min-width: 0;
}

.play-side {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.roll-row {
  display: flex;
  gap: 8px;
}

.roll-result {
  margin-top: 10px;
}
</style>
