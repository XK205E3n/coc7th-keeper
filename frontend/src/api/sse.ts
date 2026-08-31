import type { SseEventMap, SseEventName } from '../types'

export const SSE_EVENT_NAMES = [
  'round_started',
  'action_received',
  'dice_result',
  'narration',
  'state_changed',
  'perception',
  'turn_advanced',
  'character_ready',
  'scene_changed',
  'handout',
  'player_status',
  'player_removed',
] as const satisfies readonly SseEventName[]

const INITIAL_RETRY_MS = 1_000
const MAX_BACKOFF_MS = 16_000

export interface ConnectEventsOptions {
  /**
   * 玩家 token（M5.3）：EventSource 无法携带请求头，改为 `?token=` 查询参数发送，
   * 服务端以此绑定 uid 接收定向感知（perception）。
   */
  token?: string
  /** 统一事件回调：name 为事件名，data 为已解析的 JSON 载荷 */
  onEvent: (name: SseEventName, data: SseEventMap[SseEventName]) => void
  /** 每次成功建立连接（含首次与退避重连）时回调，调用方借此做 GET /api/games/{key} 全量校准 */
  onReconnect?: () => void
  /** 连接出错、即将进入退避重连时回调 */
  onError?: (event: Event) => void
}

export interface SseHandle {
  close(): void
}

/**
 * 连接房间事件流。
 * EventSource 断线后原生会自动重连，这里手动 close() 并以 1s→2s→4s→8s→16s（封顶）
 * 的指数退避自行重连；每次 onopen（成功建立连接）时回调 onReconnect()。
 */
export function connectEvents(gameKey: string, opts: ConnectEventsOptions): SseHandle {
  const params = new URLSearchParams()
  if (opts.token) {
    params.set('token', opts.token)
  }
  const qs = params.toString()
  const url = `/api/games/${encodeURIComponent(gameKey)}/events${qs ? `?${qs}` : ''}`

  let source: EventSource | null = null
  let closed = false
  let retryMs = INITIAL_RETRY_MS
  let retryTimer: number | undefined

  function open(): void {
    if (closed) return

    const es = new EventSource(url)
    source = es

    for (const name of SSE_EVENT_NAMES) {
      es.addEventListener(name, ((event: MessageEvent<string>) => {
        let data: SseEventMap[SseEventName]
        try {
          data = JSON.parse(event.data) as SseEventMap[SseEventName]
        } catch {
          data = event.data as unknown as SseEventMap[SseEventName]
        }
        opts.onEvent(name, data)
      }) as EventListener)
    }

    es.onopen = () => {
      retryMs = INITIAL_RETRY_MS
      opts.onReconnect?.()
    }

    es.onerror = (event) => {
      if (closed) return
      opts.onError?.(event)
      source?.close()
      source = null
      retryTimer = window.setTimeout(open, retryMs)
      retryMs = Math.min(retryMs * 2, MAX_BACKOFF_MS)
    }
  }

  open()

  return {
    close() {
      closed = true
      if (retryTimer !== undefined) {
        window.clearTimeout(retryTimer)
        retryTimer = undefined
      }
      source?.close()
      source = null
    },
  }
}
