<script setup lang="ts">
import { ref } from 'vue'
import { createDiscreteApi } from 'naive-ui'
import { submitAction } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useGameStore } from '../stores/game'

const props = defineProps<{
  /** 本玩家是否已提交本轮行动 */
  submitted: boolean
  /** 当前回合号（仅展示） */
  round: number
  /** 游戏号；缺省时回退到 auth.gameKey */
  gameKey?: string
}>()

const { message } = createDiscreteApi(['message'])

const auth = useAuthStore()
const gameStore = useGameStore()

const text = ref('')
const submitting = ref(false)

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
    text.value = ''
  } catch (e) {
    message.error(e instanceof Error ? e.message : String(e))
  } finally {
    submitting.value = false
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
        :disabled="submitting"
        @click="onSubmit"
      >
        {{ submitted ? '修改行动' : '提交行动' }}
      </n-button>
      <span v-if="submitted" class="action-hint">已提交，可修改（版本递增）</span>
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
}

.action-hint {
  font-size: 12px;
  color: var(--text-3, #888);
}
</style>
