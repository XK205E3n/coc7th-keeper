import type {
  AdvanceResponse,
  AuditResponse,
  BuildCharacterPayload,
  CharacterResponse,
  CharactersResponse,
  CreateGamePayload,
  CreateGameResponse,
  GetCharacterResponse,
  GetGameResponse,
  HealthResponse,
  JoinGamePayload,
  JoinGameResponse,
  MessagesResponse,
  ModuleScenesResponse,
  ModulesResponse,
  PregensResponse,
  RollResponse,
  SubmitActionResponse,
} from '../types'

/**
 * localStorage 存储键（client 与 stores/auth.ts 共用，避免互相 import 造成循环依赖）。
 * M5（TODO-B#2）：凭证按游戏多槽存 `rg_tokens`，当前游戏 `rg_current_key`。
 */
export const STORAGE_KEYS = {
  /** Record<gameKey, {playerToken, playerUid, playerName, hostToken}> */
  tokenMap: 'rg_tokens',
  currentKey: 'rg_current_key',
  /** 默认玩家名 / 最近游戏列表 / dev_token（Overview / Admin 页维护） */
  playerName: 'rg_player_name',
  recentGames: 'rg_recent_games',
  devToken: 'rg_dev_token',
} as const

export interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** JSON 请求体；提供时自动设置 Content-Type: application/json */
  body?: unknown
  /** 为 true 时使用 X-Host-Token（房主端点，如 advance）；默认 false 使用 X-Player-Token */
  host?: boolean
  /** 是否附带鉴权头，默认 true；公开端点（如 /api/health）可传 false */
  auth?: boolean
  /** 鉴权按哪个游戏的凭证槽取 token（默认取当前游戏 rg_current_key 的槽） */
  gameKey?: string
  headers?: Record<string, string>
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface AuthSlotShape {
  playerToken?: string | null
  playerUid?: string | null
  playerName?: string | null
  hostToken?: string | null
}

function readTokenMap(): Record<string, AuthSlotShape> {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.tokenMap)
    return raw ? (JSON.parse(raw) as Record<string, AuthSlotShape>) : {}
  } catch {
    return {}
  }
}

function readStoredToken(host: boolean, gameKey?: string): string | null {
  const map = readTokenMap()
  const key = gameKey ?? localStorage.getItem(STORAGE_KEYS.currentKey)
  if (key === null) return null
  const slot = map[key]
  if (!slot) return null
  return host ? (slot.hostToken ?? null) : (slot.playerToken ?? null)
}

function buildQuery(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined) {
      search.set(key, String(value))
    }
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

async function extractErrorMessage(response: Response): Promise<string> {
  const fallback = `请求失败 (HTTP ${response.status})`
  try {
    const body: unknown = await response.json()
    if (typeof body === 'object' && body !== null) {
      const record = body as Record<string, unknown>
      if (typeof record.detail === 'string') return record.detail
      if (typeof record.message === 'string') return record.message
    }
    return fallback
  } catch {
    return fallback
  }
}

/**
 * REST 基础封装：拼接 /api 前缀、注入鉴权头、解析 JSON、非 2xx 抛 ApiError。
 */
export async function apiFetch<T>(path: string, opts: ApiRequestOptions = {}): Promise<T> {
  const { method = 'GET', body, host = false, auth = true, headers, gameKey } = opts

  const requestHeaders = new Headers(headers)
  if (body !== undefined) {
    requestHeaders.set('Content-Type', 'application/json')
  }
  if (auth) {
    const token = readStoredToken(host, gameKey)
    if (token) {
      requestHeaders.set(host ? 'X-Host-Token' : 'X-Player-Token', token)
    }
  }

  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: requestHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new Error(`网络请求失败（后端未启动或 /api 代理不可达）: /api${path}`)
  }

  if (!response.ok) {
    throw new ApiError(response.status, await extractErrorMessage(response))
  }

  return (await response.json()) as T
}

// ---------- 便捷方法 ----------

export function createGame(payload: CreateGamePayload): Promise<CreateGameResponse> {
  return apiFetch('/games', { method: 'POST', body: payload })
}

export function getGame(key: string): Promise<GetGameResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}`, { gameKey: key })
}

/** 加入房间（M5.1）：邀请凭证走 X-Join-Token 头，密码可选 */
export function joinGame(
  key: string,
  name: string,
  opts: { inviteToken?: string; password?: string } = {},
): Promise<JoinGameResponse> {
  const headers: Record<string, string> = {}
  if (opts.inviteToken) {
    headers['X-Join-Token'] = opts.inviteToken
  }
  const body: JoinGamePayload = { name }
  if (opts.password) {
    body.password = opts.password
  }
  return apiFetch(`/games/${encodeURIComponent(key)}/join`, {
    method: 'POST',
    body,
    headers,
    auth: false,
  })
}

/** 房主轮换邀请凭证（旧码立即失效） */
export function refreshInvite(key: string): Promise<{ invite_token: string }> {
  return apiFetch(`/games/${encodeURIComponent(key)}/invite`, {
    method: 'POST',
    host: true,
    gameKey: key,
  })
}

/** 玩家暂离/回归（M5.2） */
export function setAway(key: string, away: boolean): Promise<{ uid: string; is_away: boolean }> {
  return apiFetch(`/games/${encodeURIComponent(key)}/${away ? 'away' : 'back'}`, {
    method: 'POST',
    gameKey: key,
  })
}

/** 房主移除玩家（M5.4） */
export function kickPlayer(key: string, uid: string): Promise<{ removed: string }> {
  return apiFetch(`/games/${encodeURIComponent(key)}/kick`, {
    method: 'POST',
    body: { uid },
    host: true,
    gameKey: key,
  })
}

export function buildCharacter(
  key: string,
  payload: BuildCharacterPayload,
  needHost = false,
): Promise<CharacterResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}/characters`, {
    method: 'POST',
    body: payload,
    host: needHost,
    gameKey: key,
  })
}

export function getCharacters(key: string): Promise<CharactersResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}/characters`, { gameKey: key })
}

export function getCharacter(key: string, playerName: string): Promise<GetCharacterResponse> {
  return apiFetch(
    `/games/${encodeURIComponent(key)}/characters/${encodeURIComponent(playerName)}`,
    { gameKey: key },
  )
}

export function submitAction(key: string, text: string): Promise<SubmitActionResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}/actions`, {
    method: 'POST',
    body: { text },
    gameKey: key,
  })
}

/** 局内聊天（M7 额外任务）：text 文本，expr 可选——带上则服务端联掷并分享结果 */
export function sendChat(
  key: string,
  payload: { text?: string; expr?: string },
): Promise<{ accepted: boolean; message: Record<string, unknown> }> {
  return apiFetch(`/games/${encodeURIComponent(key)}/chat`, {
    method: 'POST',
    body: payload,
    gameKey: key,
  })
}

export function freeRoll(key: string, expr: string, why?: string): Promise<RollResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}/roll`, {
    method: 'POST',
    body: why !== undefined ? { expr, why } : { expr },
    gameKey: key,
  })
}

export function getAudit(key: string, last?: number): Promise<AuditResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}/audit${buildQuery({ last })}`, {
    gameKey: key,
  })
}

/** 房主操作：推进回合（需要 X-Host-Token） */
export function advanceRound(key: string): Promise<AdvanceResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}/advance`, {
    method: 'POST',
    host: true,
    gameKey: key,
  })
}

/** 房主调整本局 LLM 输出上限（1000–32000；达到上限被截断时调高） */
export function setLlmLimit(key: string, maxTokens: number): Promise<{ max_tokens: number }> {
  return apiFetch(`/games/${encodeURIComponent(key)}/llm-limit`, {
    method: 'POST',
    body: { max_tokens: maxTokens },
    host: true,
    gameKey: key,
  })
}

export function getModules(): Promise<ModulesResponse> {
  return apiFetch('/modules')
}

export function getModuleScenes(moduleId: string): Promise<ModuleScenesResponse> {
  return apiFetch(`/modules/${encodeURIComponent(moduleId)}/scenes`)
}

export function getModulePregens(moduleId: string): Promise<PregensResponse> {
  return apiFetch(`/modules/${encodeURIComponent(moduleId)}/pregens`)
}

/** 叙事流消息（需玩家令牌）：SSE 重连/刷新后的全量校准 */
export function getMessages(key: string, last = 100): Promise<MessagesResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}/messages?last=${last}`, { gameKey: key })
}

/** 健康检查：公开端点，不附带鉴权头 */
export function getHealth(): Promise<HealthResponse> {
  return apiFetch('/health', { auth: false })
}

// ---------- M5.5 开发者只读监视 ----------

export type DevResource =
  | 'messages'
  | 'kp_notes'
  | 'dice_log'
  | 'state_changes'
  | 'perceptions'
  | 'llm_log'
  | 'clues'

/** 开发者令牌鉴头（Admin 页/调试用） */
export function devHeaders(devToken: string): Record<string, string> {
  return { 'X-Dev-Token': devToken }
}

export function getDevGames(devToken: string): Promise<{ games: unknown[] }> {
  return apiFetch('/dev/games', { auth: false, headers: devHeaders(devToken) })
}

export function getDevRoom(
  gameKey: string,
  devToken: string,
): Promise<Record<string, unknown>> {
  return apiFetch(`/dev/games/${encodeURIComponent(gameKey)}/room`, {
    auth: false,
    headers: devHeaders(devToken),
  })
}

export function getDevResource(
  gameKey: string,
  resource: DevResource,
  devToken: string,
): Promise<Record<string, unknown>> {
  return apiFetch(`/dev/games/${encodeURIComponent(gameKey)}/${resource}`, {
    auth: false,
    headers: devHeaders(devToken),
  })
}
