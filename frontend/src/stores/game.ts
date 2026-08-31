import { ref } from 'vue'
import { defineStore } from 'pinia'
import { getMessages } from '../api/client'
import type {
  ActionReceivedEvent,
  CharacterReadyEvent,
  GameView,
  HandoutEvent,
  PerceptionEvent,
  PlayerInfo,
  RoundStartedEvent,
  SceneChangedEvent,
  SseEventMap,
  SseEventName,
  TurnAdvancedEvent,
} from '../types'
import { useAuthStore } from './auth'

/** 叙事流 / 消息流中的一条（由 SSE 事件 append 或 loadMessages 合并而来） */
export interface MessageEntry {
  id: number
  round: number
  kind: string
  payload: unknown
}

/** 局内聊天一条（M7 额外任务） */
export interface ChatEntry {
  id: number
  uid: string
  name: string
  text: string
  expr?: string
  total?: number
  rolls?: number[]
  ts?: number
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

/**
 * 本地 SSE 追加消息的 id 基址：远大于服务端自增 id（1..N），
 * 保证「按 id 去重 / 排序」时本地条目不会被服务端消息误覆盖。
 */
const LOCAL_ID_BASE = 1_000_000_000

function makeIdGenerator(): () => number {
  let next = 1
  return () => next++
}

/**
 * 消息内容签名：同一事件在 SSE 实时流与服务端持久化消息里是两种表示
 * （如 dice_result 事件 vs kind='dice' 消息），用签名识别「同一件事」，
 * 供 SSE 历史回放去重与 loadMessages 合并去重。
 *
 * 注意：scene / handout 事件载荷不带 round（重连回放时 round 会漂移），
 * 因此这两类签名不含 round，只按载荷去重。
 */
function messageSignature(m: { kind: string; round: number; payload: unknown }): string {
  const p = (m.payload ?? {}) as Record<string, unknown>
  switch (m.kind) {
    case 'dice':
      return `dice:${m.round}:${String(p.player_uid ?? p.uid ?? '')}:${String(p.skill ?? '')}:${String(p.roll ?? '')}:${String(p.expr ?? '')}:${String(p.total ?? '')}`
    case 'narration':
      return `narration:${m.round}:${String(p.text ?? '')}`
    case 'scene':
      return `scene:${JSON.stringify(p)}`
    case 'handout':
      return `handout:${JSON.stringify(p)}`
    default:
      return `${m.kind}:${m.round}:${JSON.stringify(p)}`
  }
}

export const useGameStore = defineStore('game', () => {
  /** 公共视图（全量校准结果） */
  const game = ref<GameView | null>(null)
  /** 叙事流：SSE 事件按序追加 + 服务端消息合并（不含 chat） */
  const messages = ref<MessageEntry[]>([])
  /** 局内聊天（M7 额外任务）：独立于叙事流，刷新后从服务端消息恢复 */
  const chats = ref<ChatEntry[]>([])
  const round = ref(0)
  const phase = ref<string | null>(null)
  const players = ref<PlayerInfo[]>([])
  /** 仅包含发给我的感知 */
  const perceptions = ref<PerceptionEntry[]>([])
  /** 本玩家是否已提交行动 */
  const actionsSubmitted = ref<ActionsSubmittedState>({ submitted: false, actionVersion: null })

  const nextMessageId = makeIdGenerator()
  const nextPerceptionId = makeIdGenerator()
  const nextChatId = makeIdGenerator()

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

  /** 追加一条聊天（SSE 实时 / 服务端恢复共用） */
  function appendChat(payload: Record<string, unknown>): void {
    const entry: ChatEntry = {
      id: LOCAL_ID_BASE + nextChatId(),
      uid: String(payload.uid ?? ''),
      name: String(payload.name ?? ''),
      text: String(payload.text ?? ''),
      expr: typeof payload.expr === 'string' ? payload.expr : undefined,
      total: typeof payload.total === 'number' ? payload.total : undefined,
      rolls: Array.isArray(payload.rolls) ? (payload.rolls as number[]) : undefined,
      ts: typeof payload.ts === 'number' ? payload.ts : Date.now(),
    }
    chats.value.push(entry)
  }

  function appendMessage(payload: unknown, kind: string, eventRound?: number): void {
    const entry: MessageEntry = {
      id: LOCAL_ID_BASE + nextMessageId(),
      round: eventRound ?? round.value,
      kind,
      payload,
    }
    // SSE 历史回放去重：同一事件（同签名）已存在则跳过，避免重连后重复渲染
    if (messages.value.some((m) => messageSignature(m) === messageSignature(entry))) return
    messages.value.push(entry)
  }

  /**
   * 拉取服务端叙事流消息并合并进本地（M4）：
   * - 本地 SSE 追加的条目若与服务端消息同签名，以服务端版本为准（去重）；
   * - 按 id 去重、按 id 排序；
   * - 聊天消息（kind=chat）拆进 chats（M7），叙事流保持纯净。
   */
  async function loadMessages(key: string, last = 100): Promise<void> {
    const res = await getMessages(key, last)
    const incoming = res.messages
    // 聊天拆分
    const chatMsgs = incoming.filter((m) => m.kind === 'chat')
    for (const m of chatMsgs) {
      appendChat((m.payload ?? {}) as Record<string, unknown>)
    }
    const nonChat = incoming.filter((m) => m.kind !== 'chat')
    const incomingSigs = new Set(nonChat.map((m) => messageSignature(m)))
    messages.value = messages.value.filter((m) => !incomingSigs.has(messageSignature(m)))
    const byId = new Map<number, MessageEntry>()
    for (const m of messages.value) byId.set(m.id, m)
    for (const m of nonChat) {
      byId.set(m.id, { id: m.id, round: m.round, kind: m.kind, payload: m.payload })
    }
    messages.value = [...byId.values()].sort((a, b) => a.id - b.id)
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
      // 历史回放去重：同文本不重复追加
      if (perceptions.value.some((p) => p.text === data.text)) return
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

  /** SSE 统一事件入口：按事件名更新本地状态（M4 联调直接复用） */
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
        // 事件名 → 消息 kind：dice_result 对应服务端持久化的 'dice' 消息
        const payload = data as { round?: unknown }
        const eventRound = typeof payload.round === 'number' ? payload.round : undefined
        const kind = name === 'dice_result' ? 'dice' : name
        appendMessage(data, kind, eventRound)
        break
      }
      case 'scene_changed': {
        const ev = data as SceneChangedEvent
        const scene = ev.scene
        appendMessage(
          { text: `${scene.name} · ${scene.location}\n${scene.summary}`, scene_id: scene.id },
          'scene',
        )
        // 同步当前场景 id，顶部场景名实时更新
        if (game.value !== null) {
          game.value.current_scene = scene.id
        }
        break
      }
      case 'handout': {
        const ev = data as HandoutEvent
        appendMessage({ file: ev.file }, 'handout')
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
      case 'player_status': {
        // M5.2：暂离/回归同步玩家列表
        const status = data as { uid: string; is_away: boolean }
        const p = players.value.find((x) => x.uid === status.uid)
        if (p) {
          p.is_away = status.is_away
        }
        break
      }
      case 'player_removed': {
        // M5.4：房主踢人——从列表移除；被移除的是自己则重置
        const removed = data as { uid: string }
        const auth = useAuthStore()
        const wasMe = removed.uid === auth.playerUid
        players.value = players.value.filter((x) => x.uid !== removed.uid)
        if (wasMe) {
          reset()
        }
        break
      }
      case 'chat': {
        // M7 额外任务：局内聊天进独立 chats，不进叙事流
        appendChat(data as Record<string, unknown>)
        break
      }
    }
  }

  /** 退出房间 / 切换游戏时重置全部状态 */
  function reset(): void {
    game.value = null
    messages.value = []
    chats.value = []
    round.value = 0
    phase.value = null
    players.value = []
    perceptions.value = []
    actionsSubmitted.value = { submitted: false, actionVersion: null }
  }

  return {
    game,
    messages,
    chats,
    round,
    phase,
    players,
    perceptions,
    actionsSubmitted,
    setGame,
    loadMessages,
    onEvent,
    reset,
  }
})
