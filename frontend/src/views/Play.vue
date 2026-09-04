<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDialog, useMessage } from 'naive-ui'
import { getCharacters, getGame, getModuleScenes, getMyAction } from '../api/client'
import { connectEvents } from '../api/sse'
import type { SseHandle } from '../api/sse'
import { useAuthStore } from '../stores/auth'
import { useGameStore } from '../stores/game'
import NarrationStream from '../components/NarrationStream.vue'
import PlayerList from '../components/PlayerList.vue'
import PerceptionPanel from '../components/PerceptionPanel.vue'
import ActionInput from '../components/ActionInput.vue'
import GmPanel from '../components/GmPanel.vue'
import SceneBar from '../components/SceneBar.vue'
import CharacterBar from '../components/CharacterBar.vue'
import ChatPanel from '../components/ChatPanel.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const gameStore = useGameStore()

const gameKey = computed(() => (typeof route.params.key === 'string' ? route.params.key : ''))
const dialog = useDialog()
const message = useMessage()
/** M5（TODO-B#2）：凭证按游戏多槽——取本游戏槽，无槽即未加入 */
const hasToken = computed(() => {
  if (!gameKey.value) return false
  return auth.getTokensFor(gameKey.value).playerToken != null
})
const myUid = computed(() => {
  if (!gameKey.value) return null
  return auth.getTokensFor(gameKey.value).playerUid ?? null
})
/** 当前玩家是否房主（本游戏槽有 host_token 且公共视图中 is_host） */
const isHost = computed(() => {
  if (!gameKey.value) return false
  const slot = auth.getTokensFor(gameKey.value)
  if (!slot.hostToken) return false
  return gameStore.players.some((p) => p.uid === myUid.value && p.is_host)
})

// ---------- 场景信息（M7 视觉优化：场景栏常驻；表侧投影，无 KP 摘要） ----------
interface SceneInfo {
  name: string
  location: string
  /** 玩家可见的场景入场白（模组 scenes.json 的 intro；可能缺失） */
  brief: string
}
const sceneInfoMap = ref<Record<string, SceneInfo>>({})
const currentSceneInfo = computed<SceneInfo | null>(() => {
  const id = gameStore.game?.current_scene
  if (!id) return null
  return sceneInfoMap.value[id] ?? null
})

/** T-A2：移动端右栏折叠开关（仅 ≤640px 生效；平板/桌面恒展开） */
const sideOpen = ref(true)

const PHASE_LABELS: Record<string, string> = {
  lobby: '大厅（开局准备）',
  collecting: '收集行动',
  adjudicating: '判定中',
  narrating: '叙事中',
}

// ---------- M8R5：回合流程可视化 ----------

/** 等待提交行动的玩家名（活跃玩家中未提交者） */
const pendingNames = computed(() =>
  gameStore.players
    .filter((p) => !p.is_away && !p.has_submitted)
    .map((p) => p.name),
)
const allSubmitted = computed(
  () => gameStore.players.length > 0 && pendingNames.value.length === 0,
)
/** 行动回显：我本轮提交的文本（仅当前回合有效） */
const myActionEcho = computed(() => {
  if (gameStore.myActionRound !== gameStore.round) return null
  return gameStore.myActionText
})

watch(
  () => gameStore.roomClosed,
  (closed) => {
    if (!closed) return
    dialog.warning({
      title: '房间已关闭',
      content: '房主已关闭本房间，点击确定返回首页。',
      positiveText: '确定',
      closable: false,
      maskClosable: false,
      onPositiveClick: () => {
        gameStore.reset()
        void router.push('/')
      },
    })
  },
)

watch(
  () => gameStore.settleSkippedNames,
  (names) => {
    if (names && names.length > 0) {
      message.info(`强制推进：已跳过未提交行动的玩家（${names.join('、')}）`)
      gameStore.settleSkippedNames = null
    }
  },
)
const phaseLabel = computed(() => {
  const p = gameStore.phase
  return p !== null ? (PHASE_LABELS[p] ?? p) : '—'
})

// ---------- 我的角色（M7 视觉优化：角色信息栏常驻） ----------
const myCharacter = ref<Record<string, unknown> | null>(null)
async function refreshMyCharacter(): Promise<void> {
  if (!gameKey.value || !myUid.value) return
  try {
    const res = await getCharacters(gameKey.value)
    for (const c of res.characters) {
      if (c.uid === myUid.value) {
        myCharacter.value = c.data
        return
      }
    }
    myCharacter.value = null
  } catch {
    // 角色读失败不阻塞游玩
  }
}
function onEventSafe(name: Parameters<typeof gameStore.onEvent>[0],
                    data: Parameters<typeof gameStore.onEvent>[1]): void {
  gameStore.onEvent(name, data)
  // 状态变动/回合推进后刷新角色数值（HP/SAN/线索）
  if (name === 'state_changed' || name === 'round_started' || name === 'narration') {
    void refreshMyCharacter()
  }
}

let sseHandle: SseHandle | null = null
/** 初始化代际号：路由快速切换时丢弃过期初始化，避免旧房间数据串台 */
let initSeq = 0

/** 房间加载失败（不存在/404/网络错误）时给出明确错误页，不再卡"加载中" */
const loadFailed = ref(false)
const failMessage = ref('')

/** M8R5：房主在自己面板关闭房间后跳回首页 */
function onRoomClosedByHost(): void {
  gameStore.reset()
  void router.push('/')
}

async function initGame(): Promise<void> {
  const seq = ++initSeq
  sseHandle?.close()
  sseHandle = null
  // 切换游戏时清掉上一个房间的残留状态
  gameStore.reset()
  sceneInfoMap.value = {}
  myCharacter.value = null
  loadFailed.value = false
  failMessage.value = ''
  if (!gameKey.value || !hasToken.value) return
  try {
    const view = await getGame(gameKey.value)
    if (seq !== initSeq) return
    gameStore.setGame(view.game)
    await gameStore.loadMessages(gameKey.value)
    if (view.game.module_id) {
      try {
        const scenes = await getModuleScenes(view.game.module_id)
        const map: Record<string, SceneInfo> = {}
        for (const s of scenes.scenes) {
          map[s.id] = {
            name: s.name ?? s.id,
            location: s.location ?? '',
            brief: s.intro ?? '',
          }
        }
        sceneInfoMap.value = map
      } catch {
        // 场景信息拉取失败不阻塞游玩（场景栏显示 id）
      }
    }
    await refreshMyCharacter()
    // M8R5 行动回显：刷新后恢复自己本轮已提交的行动文本
    if (gameStore.actionsSubmitted.submitted || gameStore.myActionText === null) {
      try {
        const mine = await getMyAction(gameKey.value)
        if (seq !== initSeq) return
        gameStore.myActionText = mine.text
        gameStore.myActionRound = mine.round
      } catch {
        // 恢复失败不阻塞游玩
      }
    }
    const handle = connectEvents(gameKey.value, {
      token: auth.getTokensFor(gameKey.value).playerToken ?? undefined,
      onEvent: onEventSafe,
      onReconnect: () => {
        getGame(gameKey.value)
          .then((v) => gameStore.setGame(v.game))
          .catch(() => {})
        gameStore.loadMessages(gameKey.value).catch(() => {})
        void refreshMyCharacter()
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
  sideOpen.value = true
  initGame()
})

onUnmounted(() => {
  initSeq += 1
  sseHandle?.close()
  sseHandle = null
})
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
      <!-- 房间标题行 -->
      <div class="room-head">
        <h2 class="play-title">{{ gameStore.game?.name ?? '加载中…' }}</h2>
        <n-tag v-if="isHost" size="small" type="error" :bordered="false">房主</n-tag>
      </div>

      <!-- M8R5：回合流程状态条（等待名单 / LLM 结算状态 / 失败原因） -->
      <div class="flow-status">
        <n-alert
          v-if="gameStore.llmBusy"
          type="info"
          :bordered="false"
          class="flow-item"
        >
          AI 结算中…（裁判 → 掷骰 → 叙事）
        </n-alert>
        <n-alert
          v-else-if="gameStore.llmError"
          type="error"
          :bordered="false"
          class="flow-item"
        >
          {{ gameStore.llmError }} —— 本回合仍可修改/重新提交行动以再次触发结算。
        </n-alert>
        <n-alert
          v-else-if="allSubmitted"
          type="success"
          :bordered="false"
          class="flow-item"
        >
          全员已提交，AI 正在进入结算…
        </n-alert>
        <n-alert
          v-else-if="pendingNames.length > 0 && gameStore.phase === 'collecting'"
          type="default"
          :bordered="false"
          class="flow-item"
        >
          等待提交：{{ pendingNames.join('、') }}
        </n-alert>
      </div>

      <!-- 场景栏（常驻；brief 为玩家可见入场白，不展示 KP 摘要） -->
      <SceneBar
        :name="currentSceneInfo?.name ?? gameStore.game?.current_scene ?? '—'"
        :location="currentSceneInfo?.location"
        :brief="currentSceneInfo?.brief"
        :round="gameStore.round"
        :phase-label="phaseLabel"
      />

      <div class="play-layout">
        <!-- 主区：叙事流 -->
        <div class="play-main">
          <n-button
            class="side-toggle"
            size="small"
            :secondary="sideOpen"
            @click="sideOpen = !sideOpen"
          >
            {{ sideOpen ? '收起信息面板' : '展开信息面板' }}
          </n-button>
          <NarrationStream :messages="gameStore.messages" />
        </div>

        <!-- 右栏（常驻信息区块，移动端可折叠） -->
        <aside class="play-side" :class="{ collapsed: !sideOpen }">
          <GmPanel
            v-if="isHost"
            :game-key="gameKey"
            :max-tokens="gameStore.game?.max_tokens ?? null"
            :limit-hit="gameStore.llmLimitHit"
            @closed="onRoomClosedByHost"
          />
          <CharacterBar :character="myCharacter" />
          <!-- M8R5（E3n 定位）：行动卡片置于右栏第二位；推进/强制推进按钮内聚于此 -->
          <ActionInput
            :submitted="gameStore.actionsSubmitted.submitted"
            :round="gameStore.round"
            :game-key="gameKey"
            :all-submitted="allSubmitted"
            :is-host="isHost"
            :pending-names="pendingNames"
            :advancing="gameStore.llmBusy"
            :my-text="myActionEcho"
          />
          <PlayerList
            :players="gameStore.players"
            :my-uid="myUid"
            :is-host="isHost"
            :game-key="gameKey"
          />
          <PerceptionPanel :perceptions="gameStore.perceptions" />
          <ChatPanel :game-key="gameKey" :my-uid="myUid ?? undefined" :chats="gameStore.chats" />
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.flow-status {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}
.flow-item {
  --n-padding: 8px 12px;
}
.my-action-echo {
  font-size: 13px;
  color: var(--text-3, #9d94ad);
  padding: 6px 10px;
  border-left: 3px solid rgba(167, 139, 250, 0.5);
  background: rgba(167, 139, 250, 0.06);
  border-radius: 0 6px 6px 0;
  margin-bottom: 8px;
}
.room-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.play-title {
  margin: 0;
  font-size: 22px;
  color: var(--text);
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

/* T-A2：面板开关按钮，默认桌面/平板隐藏，仅移动端出现 */
.side-toggle {
  display: none;
  margin-bottom: 12px;
}

.play-side {
  width: 330px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* T-A2 移动端（≤640px）：单列、叙事优先、右栏可折叠 */
@media (max-width: 640px) {
  .play-layout {
    flex-direction: column;
    gap: 12px;
  }

  .side-toggle {
    display: inline-flex;
  }

  .play-side {
    width: 100%;
  }

  .play-side.collapsed {
    display: none;
  }
}

/* T-A2 平板（641–1024px）：保留双栏，右栏收紧到 280px */
@media (min-width: 641px) and (max-width: 1024px) {
  .play-side {
    width: 280px;
  }
}
</style>
