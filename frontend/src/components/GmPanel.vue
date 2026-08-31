<script setup lang="ts">
import { ref } from 'vue'
import { createDiscreteApi } from 'naive-ui'
import { advanceRound, refreshInvite } from '../api/client'

const { message } = createDiscreteApi(['message'])

const props = defineProps<{
  gameKey: string
}>()

const inviteUrl = ref('')
const refreshing = ref(false)
const advancing = ref(false)

function buildInviteUrl(inviteToken: string): string {
  // M6.1：外网化——部署在隧道/反代后可用 VITE_SHARE_URL 指定公网地址，缺省用当前地址
  const base = (import.meta.env.VITE_SHARE_URL as string | undefined) ?? window.location.origin
  return `${base}${window.location.pathname}?key=${encodeURIComponent(
    props.gameKey,
  )}&invite=${encodeURIComponent(inviteToken)}`
}

async function onRefreshInvite(): Promise<void> {
  refreshing.value = true
  try {
    const res = await refreshInvite(props.gameKey)
    inviteUrl.value = buildInviteUrl(res.invite_token)
  } catch (e) {
    message.error(`生成邀请链接失败：${e instanceof Error ? e.message : String(e)}`)
  } finally {
    refreshing.value = false
  }
}

async function onCopyInvite(): Promise<void> {
  if (!inviteUrl.value) {
    await onRefreshInvite()
  }
  if (!inviteUrl.value) return
  try {
    await navigator.clipboard.writeText(inviteUrl.value)
    message.success('邀请链接已复制，发给朋友即可加入')
  } catch {
    message.warning(`无法自动复制，请手动复制：\n${inviteUrl.value}`)
  }
}

async function onAdvance(): Promise<void> {
  advancing.value = true
  try {
    const res = await advanceRound(props.gameKey)
    message.success(`已强制推进到第 ${res.round} 轮`)
  } catch (e) {
    message.error(`推进失败：${e instanceof Error ? e.message : String(e)}`)
  } finally {
    advancing.value = false
  }
}
</script>

<template>
  <n-card title="房主面板" size="small">
    <div class="gm-panel">
      <n-space vertical size="small">
        <div class="row">
          <n-button size="small" type="primary" :loading="refreshing" @click="onCopyInvite">
            复制邀请链接
          </n-button>
          <n-button size="small" :loading="refreshing" @click="onRefreshInvite">刷新</n-button>
        </div>
        <n-input
          v-if="inviteUrl"
          :value="inviteUrl"
          readonly
          size="small"
          placeholder="点击「复制邀请链接」生成"
        />
        <n-button size="small" type="warning" :loading="advancing" @click="onAdvance">
          强制推进回合（防卡死）
        </n-button>
        <n-text depth="3" class="hint">
          房主仅管理房间，不参与剧情、不看守密人笔记。
        </n-text>
      </n-space>
    </div>
  </n-card>
</template>

<style scoped>
.gm-panel {
  width: 100%;
}
.row {
  display: flex;
  gap: 8px;
}
.hint {
  font-size: 12px;
}
</style>
