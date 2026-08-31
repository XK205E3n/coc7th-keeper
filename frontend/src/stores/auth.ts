import { ref } from 'vue'
import { defineStore } from 'pinia'
import { STORAGE_KEYS } from '../api/client'

/**
 * 玩家 / 房主鉴权信息，localStorage 持久化。
 * localStorage 键与 client.ts 共用（STORAGE_KEYS），client 直接读 localStorage，
 * 避免 client ↔ store 循环依赖。
 */
export interface SaveAuthPayload {
  playerToken?: string | null
  hostToken?: string | null
  gameKey?: string | null
  playerUid?: string | null
  playerName?: string | null
}

function readStored(key: string): string | null {
  return localStorage.getItem(key)
}

export const useAuthStore = defineStore('auth', () => {
  const playerToken = ref<string | null>(readStored(STORAGE_KEYS.playerToken))
  const hostToken = ref<string | null>(readStored(STORAGE_KEYS.hostToken))
  const gameKey = ref<string | null>(readStored(STORAGE_KEYS.gameKey))
  const playerUid = ref<string | null>(readStored(STORAGE_KEYS.playerUid))
  const playerName = ref<string | null>(readStored(STORAGE_KEYS.playerName))

  function persist(key: string, value: string | null): void {
    if (value === null) {
      localStorage.removeItem(key)
    } else {
      localStorage.setItem(key, value)
    }
  }

  /** 局部更新鉴权信息：只覆盖传入的字段，并同步到 localStorage */
  function saveAuth(payload: SaveAuthPayload): void {
    if (payload.playerToken !== undefined) {
      playerToken.value = payload.playerToken
      persist(STORAGE_KEYS.playerToken, payload.playerToken)
    }
    if (payload.hostToken !== undefined) {
      hostToken.value = payload.hostToken
      persist(STORAGE_KEYS.hostToken, payload.hostToken)
    }
    if (payload.gameKey !== undefined) {
      gameKey.value = payload.gameKey
      persist(STORAGE_KEYS.gameKey, payload.gameKey)
    }
    if (payload.playerUid !== undefined) {
      playerUid.value = payload.playerUid
      persist(STORAGE_KEYS.playerUid, payload.playerUid)
    }
    if (payload.playerName !== undefined) {
      playerName.value = payload.playerName
      persist(STORAGE_KEYS.playerName, payload.playerName)
    }
  }

  /** 清空全部鉴权信息（退出房间 / 重新建团时调用） */
  function clear(): void {
    saveAuth({
      playerToken: null,
      hostToken: null,
      gameKey: null,
      playerUid: null,
      playerName: null,
    })
  }

  return {
    playerToken,
    hostToken,
    gameKey,
    playerUid,
    playerName,
    saveAuth,
    clear,
  }
})
