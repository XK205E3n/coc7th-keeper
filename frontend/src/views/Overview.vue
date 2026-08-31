<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createDiscreteApi } from 'naive-ui'
import {
  createGame,
  getGame,
  getHealth,
  getModules,
  joinGame,
  STORAGE_KEYS,
} from '../api/client'
import { useAuthStore } from '../stores/auth'
import type { ModuleInfo } from '../types'

const { message } = createDiscreteApi(['message'])

const router = useRouter()
const auth = useAuthStore()

// ---------- 后端状态 ----------
const status = ref<string>('检测中…')
const healthError = ref<string | null>(null)

// ---------- 创建冒险 ----------
const createName = ref('')
const createModuleId = ref<string | null>(null)
const createPassword = ref('')
const modules = ref<ModuleInfo[]>([])
const creating = ref(false)

// ---------- 加入游戏 ----------
const joinKey = ref('')
const joinInvite = ref('')
const joinPassword = ref('')
const joining = ref(false)

// ---------- 玩家名（localStorage rg_player_name） ----------
const playerName = ref(localStorage.getItem(STORAGE_KEYS.playerName) ?? '')

// ---------- 最近游戏（localStorage rg_recent_games） ----------
interface RecentGame {
  key: string
  name: string
  ts: number
}
const recentGames = ref<RecentGame[]>([])

function readRecentGames(): RecentGame[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.recentGames)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as RecentGame[]) : []
  } catch {
    return []
  }
}

function writeRecentGames(list: RecentGame[]): void {
  localStorage.setItem(STORAGE_KEYS.recentGames, JSON.stringify(list.slice(0, 8)))
}

function rememberGame(key: string, name: string): void {
  const list = readRecentGames().filter((g) => g.key !== key)
  list.unshift({ key, name, ts: Date.now() })
  writeRecentGames(list)
  recentGames.value = list
}

function resolvePlayerName(): string {
  const name = playerName.value.trim()
  const final = name || '调查员'
  localStorage.setItem(STORAGE_KEYS.playerName, final)
  return final
}

onMounted(async () => {
  recentGames.value = readRecentGames()
  // M5.1：从邀请链接自动加入 ?key=xxx&invite=yyy
  const params = new URLSearchParams(window.location.search)
  const inviteKey = params.get('key')
  const inviteToken = params.get('invite')
  if (inviteKey && inviteToken) {
    await joinByInvite(inviteKey, inviteToken, params.get('password') ?? undefined)
  }
  try {
    const res = await getHealth()
    status.value = res.status === 'ok' ? '后端在线' : `未知状态: ${res.status}`
  } catch (e) {
    healthError.value = e instanceof Error ? e.message : String(e)
  }
  try {
    const res = await getModules()
    modules.value = res.modules
  } catch (e) {
    message.error(`模组列表加载失败：${e instanceof Error ? e.message : String(e)}`)
  }
})

async function onCreate(): Promise<void> {
  const name = createName.value.trim()
  if (!name) {
    message.warning('请输入冒险名称')
    return
  }
  creating.value = true
  try {
    const hostName = resolvePlayerName()
    const res = await createGame({
      name,
      module_id: createModuleId.value ?? undefined,
      host_name: hostName,
      password: createPassword.value.trim() || undefined,
    })
    // 房主同时是玩家 1：host_token 即其玩家令牌，两个头都存
    auth.saveAuth({
      gameKey: res.game_key,
      hostToken: res.host_token,
      playerToken: res.host_token,
      playerUid: res.host_uid,
      playerName: hostName,
    })
    rememberGame(res.game_key, name)
    const inviteUrl = buildInviteUrl(res.game_key, res.invite_token)
    message.success(`冒险「${name}」已创建，邀请链接已复制`)
    navigator.clipboard?.writeText(inviteUrl).catch(() => {})
    router.push(`/play/${res.game_key}`)
  } catch (e) {
    message.error(e instanceof Error ? e.message : String(e))
  } finally {
    creating.value = false
  }
}

function buildInviteUrl(key: string, inviteToken: string): string {
  return `${window.location.origin}${window.location.pathname}?key=${encodeURIComponent(key)}&invite=${encodeURIComponent(inviteToken)}`
}

async function joinByInvite(
  key: string,
  inviteToken: string,
  password?: string,
  autoName?: string,
): Promise<void> {
  joining.value = true
  try {
    const name = autoName ?? resolvePlayerName()
    const res = await joinGame(key, name, { inviteToken, password: password || undefined })
    auth.saveAuth({
      gameKey: key,
      playerToken: res.player_token,
      playerUid: res.player.uid,
      playerName: name,
      hostToken: null,
    })
    let gameName = key
    try {
      const view = await getGame(key)
      gameName = view.game.name
    } catch {
      // 名字拿不到就用游戏号兜底
    }
    rememberGame(key, gameName)
    message.success(`已通过邀请加入游戏 ${gameName}`)
    // 清掉 URL 参数，避免刷新重复加入
    window.history.replaceState({}, '', window.location.pathname)
    router.replace(`/play/${key}`)
  } catch (e) {
    window.history.replaceState({}, '', window.location.pathname)
    message.error(`加入失败：${e instanceof Error ? e.message : String(e)}`)
  } finally {
    joining.value = false
  }
}

async function onJoin(): Promise<void> {
  const key = joinKey.value.trim()
  if (!key) {
    message.warning('请输入游戏号')
    return
  }
  if (!joinInvite.value.trim()) {
    message.warning('请输入邀请码（房主分享链接中带 ?invite= 参数）')
    return
  }
  await joinByInvite(key, joinInvite.value.trim(), joinPassword.value.trim() || undefined)
}

function openRecent(g: RecentGame): void {
  router.push(`/play/${g.key}`)
}

function formatTs(ts: number): string {
  const d = new Date(ts)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<template>
  <section class="page">
    <div class="page-head">
      <h1>跑团 Web 平台</h1>
      <p class="health">
        后端状态：
        <span v-if="healthError" class="bad">{{ healthError }}</span>
        <span v-else class="ok">{{ status }}</span>
      </p>
    </div>

    <div class="overview-grid">
      <!-- 创建冒险 -->
      <n-card title="创建冒险" class="overview-card">
        <n-form label-placement="top">
          <n-form-item label="冒险名称">
            <n-input
              v-model:value="createName"
              placeholder="如：惊魂之夜"
              :disabled="creating"
              @keyup.enter="onCreate"
            />
          </n-form-item>
          <n-form-item label="模组（可选）">
            <n-select
              v-model:value="createModuleId"
              :options="modules.map((m) => ({ label: m.cn, value: m.id }))"
              placeholder="选择模组（可选）"
              clearable
              :disabled="creating"
            />
          </n-form-item>
          <n-form-item label="访问密码（可选）">
            <n-input
              v-model:value="createPassword"
              type="password"
              show-password-on="click"
              placeholder="设置后加入需密码（可选）"
              :disabled="creating"
            />
          </n-form-item>
          <n-form-item label="玩家名">
            <n-input v-model:value="playerName" placeholder="默认：调查员" :disabled="creating" />
          </n-form-item>
          <n-button type="primary" block :loading="creating" :disabled="creating" @click="onCreate">
            创建
          </n-button>
        </n-form>
      </n-card>

      <!-- 加入游戏 -->
      <n-card title="加入游戏" class="overview-card">
        <n-form label-placement="top">
          <n-form-item label="游戏号">
            <n-input
              v-model:value="joinKey"
              placeholder="输入房主分享的游戏号"
              :disabled="joining"
              @keyup.enter="onJoin"
            />
          </n-form-item>
          <n-form-item label="邀请码">
            <n-input
              v-model:value="joinInvite"
              placeholder="邀请链接中的 ?invite= 参数（必填）"
              :disabled="joining"
              @keyup.enter="onJoin"
            />
          </n-form-item>
          <n-form-item label="访问密码（房间设置时必填）">
            <n-input
              v-model:value="joinPassword"
              type="password"
              show-password-on="click"
              placeholder="房间设置了密码时填写"
              :disabled="joining"
            />
          </n-form-item>
          <n-form-item label="玩家名">
            <n-input v-model:value="playerName" placeholder="默认：调查员" :disabled="joining" />
          </n-form-item>
          <n-button type="primary" block :loading="joining" :disabled="joining" @click="onJoin">
            加入
          </n-button>
        </n-form>
      </n-card>
    </div>

    <!-- 最近游戏 -->
    <n-card title="最近游戏" class="recent-card">
      <n-empty v-if="recentGames.length === 0" description="还没有玩过的游戏，创建或加入一个吧" />
      <n-list v-else>
        <n-list-item v-for="g in recentGames" :key="g.key" class="recent-item" @click="openRecent(g)">
          <div class="recent-row">
            <span class="recent-name">{{ g.name }}</span>
            <span class="recent-key">{{ g.key }}</span>
            <span class="recent-ts">{{ formatTs(g.ts) }}</span>
          </div>
        </n-list-item>
      </n-list>
    </n-card>
  </section>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 16px;
}

.page-head h1 {
  margin: 0;
  font-size: 22px;
}

.health {
  font-size: 13px;
  color: var(--text-3, #888);
}

.ok {
  color: var(--success-color, #18a058);
}

.bad {
  color: var(--error-color, #d03050);
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.recent-card {
  max-width: 720px;
}

.recent-item {
  cursor: pointer;
}

.recent-item:hover {
  background: rgba(128, 128, 128, 0.08);
}

.recent-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.recent-name {
  font-weight: 500;
}

.recent-key {
  font-family: monospace;
  font-size: 12px;
  color: var(--text-3, #888);
}

.recent-ts {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-3, #888);
}
</style>
