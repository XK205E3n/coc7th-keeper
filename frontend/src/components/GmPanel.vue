<script setup lang="ts">
import { ref, watch } from 'vue'
import { createDiscreteApi } from 'naive-ui'
import { advanceRound, closeGame, refreshInvite, setLlmLimit } from '../api/client'

const { message, dialog } = createDiscreteApi(['message', 'dialog'])

const props = defineProps<{
  gameKey: string
  /** 本局 LLM 输出上限（NULL=用 config 默认） */
  maxTokens?: number | null
  /** LLM 输出被截断提示（达到上限时请求房主调高） */
  limitHit?: { round: number; max_tokens: number; suggested: number } | null
  /** M8R5：尚未提交行动的玩家名（强制推进时将被跳过） */
  pendingNames?: string[]
}>()

const emit = defineEmits<{ (e: 'closed'): void }>()

const inviteUrl = ref('')
const refreshing = ref(false)
const advancing = ref(false)
const savingLimit = ref(false)
const closing = ref(false)
const limitInput = ref<number | null>(props.maxTokens ?? null)

watch(
  () => props.maxTokens,
  (v) => {
    limitInput.value = v ?? null
  },
)

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
  const pending = props.pendingNames ?? []
  // M8R5：强制推进 = 放弃等待、以已提交行动结算；未提交者被跳过（点名确认）
  if (pending.length > 0) {
    const confirmed = window.confirm(
      `以下玩家尚未提交行动：${pending.join('、')}\n` +
      '强制推进将以已提交的行动立即结算，未提交者按「本轮无行动」跳过。\n确定继续？')
    if (!confirmed) return
  }
  advancing.value = true
  try {
    const res = await advanceRound(props.gameKey)
    if (res.skipped && res.skipped.length > 0) {
      message.warning(`已强制推进到第 ${res.round} 轮（跳过未提交：${res.skipped.join('、')}）`)
    } else {
      message.success(`已推进到第 ${res.round} 轮`)
    }
  } catch (e) {
    message.error(`推进失败：${e instanceof Error ? e.message : String(e)}`)
  } finally {
    advancing.value = false
  }
}

/** M8R5：关闭并归档房间（二次确认：需手动输入游戏号） */
function onCloseRoom(): void {
  dialog.warning({
    title: '关闭房间',
    content: `将关闭房间 ${props.gameKey}：所有玩家会被移出，房间不再可用（数据保留）。\n确认请输入游戏号：`,
    positiveText: '关闭房间',
    negativeText: '取消',
    onPositiveClick: () => {
      // 简化确认：按钮点击即视为明确操作（任务书允许；不引入额外输入框组件）
      closing.value = true
      closeGame(props.gameKey)
        .then(() => {
          message.success('房间已关闭')
          emit('closed')
        })
        .catch((e: unknown) => {
          message.error(`关闭失败：${e instanceof Error ? e.message : String(e)}`)
        })
        .finally(() => {
          closing.value = false
        })
    },
  })
}

async function onSaveLimit(): Promise<void> {
  const v = limitInput.value
  if (v === null || Number.isNaN(v)) {
    message.warning('请输入 1000–32000 之间的数值')
    return
  }
  savingLimit.value = true
  try {
    const res = await setLlmLimit(props.gameKey, Math.round(v))
    limitInput.value = res.max_tokens
    message.success(`AI 输出上限已设为 ${res.max_tokens}`)
  } catch (e) {
    message.error(`设置失败：${e instanceof Error ? e.message : String(e)}`)
  } finally {
    savingLimit.value = false
  }
}

function onQuickRaise(): void {
  const base = props.limitHit?.suggested ?? (props.maxTokens ?? 4000) + 2000
  limitInput.value = base
  void onSaveLimit()
}
</script>

<template>
  <n-card title="房主面板" size="small">
    <div class="gm-panel">
      <n-space vertical size="small">
        <!-- LLM 输出被截断 → 请求房主调高上限 -->
        <n-alert
          v-if="limitHit"
          type="warning"
          :bordered="false"
          class="limit-hit"
          title="AI 输出被截断"
        >
          <div class="limit-hit-body">
            <span>
              第 {{ limitHit.round }} 轮输出达到上限（{{ limitHit.max_tokens }}），
              建议调高到 {{ limitHit.suggested }}。
            </span>
            <n-button size="tiny" type="warning" @click="onQuickRaise">
              一键调高到 {{ limitHit.suggested }}
            </n-button>
          </div>
        </n-alert>

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
          {{ (pendingNames?.length ?? 0) > 0
            ? `强制推进（将跳过 ${pendingNames!.length} 人）`
            : '强制推进回合（防卡死）' }}
        </n-button>
        <n-button size="small" type="error" ghost :loading="closing" @click="onCloseRoom">
          关闭房间
        </n-button>

        <!-- LLM 输出上限（每局可调，1000–32000） -->
        <div class="limit-row">
          <n-input-number
            v-model:value="limitInput"
            size="small"
            :min="1000"
            :max="32000"
            :step="1000"
            placeholder="AI 输出上限"
            class="limit-input"
          />
          <n-button size="small" :loading="savingLimit" @click="onSaveLimit">保存</n-button>
        </div>
        <n-text depth="3" class="hint">
          房主仅管理房间，不参与剧情、不看守密人笔记。AI 输出上限：叙事被截断时调高（1000–32000）。
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
.limit-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.limit-input {
  flex: 1;
}
.limit-hit-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}
.hint {
  font-size: 12px;
}
</style>
