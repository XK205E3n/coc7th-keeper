import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { STORAGE_KEYS } from '../api/client'

/**
 * 玩家 / 房主鉴权信息，**按游戏多槽存储**（TODO-B#2 / M5.1）。
 * - localStorage：`rg_tokens` = `Record<gameKey, Slot>`，`rg_current_key` 当前游戏
 * - `playerToken/hostToken/playerUid/playerName` 是按 currentKey 取槽的 computed，
 *   使用方（Play/Overview/Characters）写法保持不变
 * - client.ts 直接读 localStorage（STORAGE_KEYS），避免循环依赖
 */
export interface AuthSlot {
  playerToken?: string | null
  playerUid?: string | null
  playerName?: string | null
  hostToken?: string | null
}

export interface SaveAuthPayload extends AuthSlot {
  gameKey?: string | null
}

function readMap(): Record<string, AuthSlot> {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.tokenMap)
    return raw ? (JSON.parse(raw) as Record<string, AuthSlot>) : {}
  } catch {
    return {}
  }
}

function writeMap(map: Record<string, AuthSlot>): void {
  localStorage.setItem(STORAGE_KEYS.tokenMap, JSON.stringify(map))
}

function readCurrentKey(): string | null {
  return localStorage.getItem(STORAGE_KEYS.currentKey)
}

export const useAuthStore = defineStore('auth', () => {
  const tokenMap = ref<Record<string, AuthSlot>>(readMap())
  const currentKey = ref<string | null>(readCurrentKey())

  const slot = computed<AuthSlot>(() =>
    currentKey.value !== null ? tokenMap.value[currentKey.value] ?? {} : {},
  )

  /** 兼容旧字段名（M5 前单槽），保持使用方写法不变 */
  const gameKey = computed(() => currentKey.value)
  const playerToken = computed(() => slot.value.playerToken ?? null)
  const hostToken = computed(() => slot.value.hostToken ?? null)
  const playerUid = computed(() => slot.value.playerUid ?? null)
  const playerName = computed(() => slot.value.playerName ?? null)

  function persistCurrentKey(): void {
    if (currentKey.value !== null) {
      localStorage.setItem(STORAGE_KEYS.currentKey, currentKey.value)
    }
  }

  /** 写入/更新某个游戏的凭证槽，并把它设为当前游戏 */
  function saveAuth(payload: SaveAuthPayload): void {
    const key = payload.gameKey
    if (key === null) {
      return
    }
    if (key === undefined) {
      return // 必须带 gameKey
    }
    const map = { ...tokenMap.value }
    const existing = map[key] ?? {}
    map[key] = {
      playerToken: payload.playerToken !== undefined ? payload.playerToken : existing.playerToken,
      playerUid: payload.playerUid !== undefined ? payload.playerUid : existing.playerUid,
      playerName: payload.playerName !== undefined ? payload.playerName : existing.playerName,
      hostToken: payload.hostToken !== undefined ? payload.hostToken : existing.hostToken,
    }
    tokenMap.value = map
    writeMap(map)
    currentKey.value = key
    persistCurrentKey()
  }

  /** 纯读取某游戏的凭证槽（不切换当前游戏） */
  function getTokensFor(key: string): AuthSlot {
    return tokenMap.value[key] ?? {}
  }

  /** 切换当前游戏（读该游戏的凭证） */
  function selectGame(key: string): void {
    currentKey.value = key
    persistCurrentKey()
  }

  /** 清空全部凭证与当前游戏 */
  function clear(): void {
    tokenMap.value = {}
    localStorage.removeItem(STORAGE_KEYS.tokenMap)
    currentKey.value = null
    localStorage.removeItem(STORAGE_KEYS.currentKey)
    // 兼容清理 M5 前的旧单槽键
    for (const k of ['rg_player_token', 'rg_host_token', 'rg_game_key',
      'rg_player_uid', 'rg_player_name']) {
      localStorage.removeItem(k)
    }
  }

  return {
    tokenMap,
    currentKey,
    gameKey,
    playerToken,
    hostToken,
    playerUid,
    playerName,
    saveAuth,
    getTokensFor,
    selectGame,
    clear,
  }
})
