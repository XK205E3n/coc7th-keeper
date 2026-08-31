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
  JoinGameResponse,
  ModuleScenesResponse,
  ModulesResponse,
  RollResponse,
  SubmitActionResponse,
} from '../types'

/**
 * localStorage 存储键（client 与 stores/auth.ts 共用，避免互相 import 造成循环依赖）。
 */
export const STORAGE_KEYS = {
  playerToken: 'rg_player_token',
  hostToken: 'rg_host_token',
  gameKey: 'rg_game_key',
  playerUid: 'rg_player_uid',
  playerName: 'rg_player_name',
} as const

export interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** JSON 请求体；提供时自动设置 Content-Type: application/json */
  body?: unknown
  /** 为 true 时使用 X-Host-Token（房主端点，如 advance）；默认 false 使用 X-Player-Token */
  host?: boolean
  /** 是否附带鉴权头，默认 true；公开端点（如 /api/health）可传 false */
  auth?: boolean
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

function readStoredToken(host: boolean): string | null {
  return localStorage.getItem(host ? STORAGE_KEYS.hostToken : STORAGE_KEYS.playerToken)
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
  const { method = 'GET', body, host = false, auth = true, headers } = opts

  const requestHeaders = new Headers(headers)
  if (body !== undefined) {
    requestHeaders.set('Content-Type', 'application/json')
  }
  if (auth) {
    const token = readStoredToken(host)
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
  return apiFetch(`/games/${encodeURIComponent(key)}`)
}

export function joinGame(key: string, name: string): Promise<JoinGameResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}/join`, { method: 'POST', body: { name } })
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
  })
}

export function getCharacters(key: string): Promise<CharactersResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}/characters`)
}

export function getCharacter(key: string, playerName: string): Promise<GetCharacterResponse> {
  return apiFetch(
    `/games/${encodeURIComponent(key)}/characters/${encodeURIComponent(playerName)}`,
  )
}

export function submitAction(key: string, text: string): Promise<SubmitActionResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}/actions`, { method: 'POST', body: { text } })
}

export function freeRoll(key: string, expr: string, why?: string): Promise<RollResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}/roll`, {
    method: 'POST',
    body: why !== undefined ? { expr, why } : { expr },
  })
}

export function getAudit(key: string, last?: number): Promise<AuditResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}/audit${buildQuery({ last })}`)
}

/** 房主操作：推进回合（需要 X-Host-Token） */
export function advanceRound(key: string): Promise<AdvanceResponse> {
  return apiFetch(`/games/${encodeURIComponent(key)}/advance`, { method: 'POST', host: true })
}

export function getModules(): Promise<ModulesResponse> {
  return apiFetch('/modules')
}

export function getModuleScenes(moduleId: string): Promise<ModuleScenesResponse> {
  return apiFetch(`/modules/${encodeURIComponent(moduleId)}/scenes`)
}

/** 健康检查：公开端点，不附带鉴权头 */
export function getHealth(): Promise<HealthResponse> {
  return apiFetch('/health', { auth: false })
}
