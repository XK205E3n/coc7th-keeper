<script setup lang="ts">
import { ref, watch } from 'vue'
import { createDiscreteApi } from 'naive-ui'
import { advanceRound, submitAction } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useGameStore } from '../stores/game'

const props = defineProps<{
  /** 本玩家是否已提交本轮行动 */
  submitted: boolean
  /** 当前回合号（仅展示） */
  round: number
  /** 游戏号；缺省时回退到 auth.gameKey */
  gameKey?: string
  /** M8R5：活跃玩家是否已全部提交（true 时所有玩家可点「推进回合」） */
  allSubmitted?: boolean
  /** M8R5：当前玩家是否房主（未全员提交时仅房主可强制推进） */
  isHost?: boolean
  /** M8R5：尚未提交行动的玩家名 */
  pendingNames?: string[]
  /** M8R5：AI 结算进行中（推进按钮转圈） */
  advancing?: boolean
  /** M8R5：已提交的行动文本（回显到输入框，方便查看与修改） */
  myText?: string | null
}>()

const { message } = createDiscreteApi(['message'])

const auth = useAuthStore()
const gameStore = useGameStore()

const text = ref('')
const submitting = ref(false)

/** 已提交的行动文本变化（提交/新回合/刷新恢复）→ 回填输入框，方便查看与修改 */
watch(
  () => props.myText,
  (v) => {
    text.value = v ?? ''
  },
)
watch(
  () => props.round,
  () => {
    // 新回合开始：清空输入框（myText 会随 myActionRound 失效变 null）
    text.value = ''
  },
)

async function onSubmit(): Promise<void> {
  const key = props.gameKey ?? auth.gameKey
  if (!key) {
    message.warning('尚未加入游戏，无法提交行动')
    return
  }
  const content = text.value.trim()
  if (!content) {
    message.warning('请输入行动内容')
    return
  }
  submitting.value = true
  try {
    await submitAction(key, content)
    // M8R5 行动回显：记住本轮提交的文本（刷新后由 /my-action 恢复）
    gameStore.myActionText = content
    gameStore.myActionRound = props.round
    message.success('行动已提交')
  } catch (e) {
    message.error(e instanceof Error ? e.message : String(e))
  } finally {
    submitting.value = false
  }
}

/** M8R5：推进回合 —— 全员提交后任何人可点；结算期间转圈 */
async function onAdvance(): Promise<void> {
  const key = props.gameKey ?? auth.gameKey
  if (!key) return
  try {
    const res = await advanceRound(key)
    message.success(`已推进到第 ${res.round} 轮`)
  } catch (e) {
    message.error(`推进失败：${e instanceof Error ? e.message : String(e)}`)
  }
}
</script>

<template>
  <n-card title="行动" size="small">
    <div class="action-round">第 {{ round }} 轮</div>
    <n-input
      v-model:value="text"
      type="textarea"
      :rows="3"
      placeholder="描述你本回合的行动，如：我仔细检查这扇门（侦查）"
      :disabled="submitting"
    />
    <div class="action-footer">
      <n-button
        type="primary"
        :loading="submitting"
        :disabled="submitting || gameStore.llmBusy"
        @click="onSubmit"
      >
        {{ submitted ? '修改行动' : '提交行动' }}
      </n-button>

      <!-- M8R5（E3n 定案）：全员提交后「推进回合」亮起，任何人可点；不再自动推进 -->
      <n-button
        v-if="allSubmitted"
        type="success"
        :loading="advancing"
        :disabled="submitting"
        @click="onAdvance"
      >
        推进回合
      </n-button>

      <!-- M8R5：未全员提交时房主可强制推进（跳过未提交者） -->
      <n-button
        v-else-if="isHost"
        type="warning"
        :loading="advancing"
        :disabled="submitting"
        @click="onAdvance"
      >
        强制推进（将跳过 {{ pendingNames?.length ?? 0 }} 人）
      </n-button>
    </div>
    <div v-if="submitted" class="action-hint">
      已提交本轮行动，可直接修改后再次提交（版本递增）。
    </div>
  </n-card>
</template>

<style scoped>
.action-round {
  font-size: 12px;
  color: var(--text-3, #888);
  margin-bottom: 8px;
}

.action-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.action-hint {
  font-size: 12px;
  color: var(--text-3, #888);
  margin-top: 8px;
}
</style>
