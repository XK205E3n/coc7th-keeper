import { ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  ActionReceivedEvent,
  CharacterReadyEvent,
  GameView,
  PerceptionEvent,
  PlayerInfo,
  RoundStartedEvent,
  SseEventMap,
  SseEventName,
  TurnAdvancedEvent,
} from '../types'
import { useAuthStore } from './auth'

/** 叙事流 / 消息流中的一条（由 SSE 事件 append 而来） */
export interface MessageEntry {
  id: number
  round: number
  kind: string
  payload: unknown
}

/** 我的私密感知（perception，仅发给当前玩家的条目） */
export interface PerceptionEntry {
  id: number
  text: string
}

/** 当前玩家在本回合是否已提交行动 */
export interface ActionsSubmittedState {
  submitted: boolean
  actionVersion: number | null
}

function makeIdGenerator(): () => number {
  let next = 1
  return () => next++
}

export const useGameStore = defineStore('game', () => {
  /** 公共视图（全量校准结果） */
  const game = ref<GameView | null>(null)
  /** 叙事流：dice_result / narration 等事件按序追加 */
  const messages = ref<MessageEntry[]>([])
  const round = ref(0)
  const phase = ref<string | null>(null)
  const players = ref<PlayerInfo[]>([])
  /** 仅包含发给我的感知 */
  const perceptions = ref<PerceptionEntry[]>([])
  /** 本玩家是否已提交行动 */
  const actionsSubmitted = ref<ActionsSubmittedState>({ submitted: false, actionVersion: null })

  const nextMessageId = makeIdGenerator()
  const nextPerceptionId = makeIdGenerator()

  function findMyPlayer(view: GameView): PlayerInfo | null {
    const auth = useAuthStore()
    if (auth.playerUid === null) return null
    return view.players.find((p) => p.uid === auth.playerUid) ?? null
  }

  /** 从服务端公共视图全量校准本地状态 */
  function setGame(view: GameView): void {
    game.value = view
    round.value = view.round
    phase.value = view.phase
    players.value = view.players

    const mine = findMyPlayer(view)
    actionsSubmitted.value =
      mine !== null
        ? { submitted: mine.has_submitted, actionVersion: mine.action_version }
        : { submitted: false, actionVersion: null }
  }

  function appendMessage(payload: unknown, kind: string, eventRound?: number): void {
    messages.value.push({
      id: nextMessageId(),
      round: eventRound ?? round.value,
      kind,
      payload,
    })
  }

  function applyActionReceived(data: ActionReceivedEvent): void {
    for (const player of players.value) {
      if (player.uid === data.uid) {
        player.has_submitted = true
        player.action_version = data.action_version
      }
    }
    const auth = useAuthStore()
    if (data.uid === auth.playerUid) {
      actionsSubmitted.value = { submitted: true, actionVersion: data.action_version }
    }
  }

  function applyPerception(data: PerceptionEvent): void {
    const auth = useAuthStore()
    // 定向感知：只收 to 指向自己的条目（后端契约按 X-Player-Token 绑定，此处兜底过滤）
    if (auth.playerUid !== null && data.to === auth.playerUid) {
      perceptions.value.push({ id: nextPerceptionId(), text: data.text })
    }
  }

  /** 玩家就绪（角色卡就绪事件）：确保 players 列表里有该玩家 */
  function upsertPlayer(info: { uid: string; name: string }): void {
    const existing = players.value.find((p) => p.uid === info.uid)
    if (existing !== undefined) {
      existing.name = info.name
      return
    }
    players.value.push({
      uid: info.uid,
      name: info.name,
      is_host: false,
      is_away: false,
      has_submitted: false,
      action_version: null,
      joined_at: '',
    })
  }

  /** SSE 统一事件入口：按事件名更新本地状态（纯逻辑，M4 联调直接复用） */
  function onEvent(name: SseEventName, data: SseEventMap[SseEventName]): void {
    switch (name) {
      case 'round_started':
      case 'turn_advanced': {
        const turn = data as RoundStartedEvent | TurnAdvancedEvent
        round.value = turn.round
        phase.value = turn.phase
        // 新回合开始：本回合行动已提交标记重置
        actionsSubmitted.value = { submitted: false, actionVersion: null }
        break
      }
      case 'action_received': {
        applyActionReceived(data as ActionReceivedEvent)
        break
      }
      case 'dice_result':
      case 'narration':
      case 'state_changed': {
        // state_changed 的载荷是宽松 Record，用收缩检查取 round（存在才用）
        const payload = data as { round?: unknown }
        const eventRound = typeof payload.round === 'number' ? payload.round : undefined
        appendMessage(data, name, eventRound)
        break
      }
      case 'perception': {
        applyPerception(data as PerceptionEvent)
        break
      }
      case 'character_ready': {
        const ready = data as CharacterReadyEvent
        upsertPlayer({ uid: ready.uid, name: ready.name })
        break
      }
    }
  }

  /** 退出房间 / 刷新场景时重置全部状态 */
  function reset(): void {
    game.value = null
    messages.value = []
    round.value = 0
    phase.value = null
    players.value = []
    perceptions.value = []
    actionsSubmitted.value = { submitted: false, actionVersion: null }
  }

  return {
    game,
    messages,
    round,
    phase,
    players,
    perceptions,
    actionsSubmitted,
    setGame,
    onEvent,
    reset,
  }
})
