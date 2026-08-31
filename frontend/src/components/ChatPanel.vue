<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { createDiscreteApi } from 'naive-ui'
import { sendChat } from '../api/client'
import type { ChatEntry } from '../stores/game'

const { message } = createDiscreteApi(['message'])

const props = defineProps<{
  gameKey: string
  myUid?: string | null
  chats: ChatEntry[]
}>()

const input = ref('')
const sending = ref(false)
const listEl = ref<HTMLElement | null>(null)

// 新消息自动滚到底部
watch(
  () => props.chats.length,
  async () => {
    await nextTick()
    if (listEl.value) {
      listEl.value.scrollTop = listEl.value.scrollHeight
    }
  },
)

function formatTs(ts: number | undefined): string {
  if (!ts) return ''
  const d = new Date(ts)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function post(payload: { text?: string; expr?: string }): Promise<void> {
  sending.value = true
  try {
    await sendChat(props.gameKey, payload)
    input.value = ''
  } catch (e) {
    message.error(e instanceof Error ? e.message : String(e))
  } finally {
    sending.value = false
  }
}

function onSend(): void {
  const text = input.value.trim()
  if (!text) return
  void post({ text })
}

function onRoll(): void {
  const expr = input.value.trim()
  if (!expr) {
    message.warning('请输入骰子表达式，如 1d100 或 2d6+3')
    return
  }
  void post({ expr })
}
</script>

<template>
  <n-card title="聊天" size="small" class="chat-panel">
    <div ref="listEl" class="chat-list">
      <n-empty v-if="chats.length === 0" description="聊聊你的发现吧" size="small" />
      <div v-for="c in chats" :key="c.id" class="chat-item">
        <span class="chat-name" :class="{ me: c.uid === myUid }">{{ c.name }}</span>
        <span class="chat-time">{{ formatTs(c.ts) }}</span>
        <div v-if="c.text" class="chat-text">{{ c.text }}</div>
        <div v-if="c.expr" class="chat-roll">
          🎲 {{ c.expr }} = <b>{{ c.total }}</b>
          <span v-if="c.rolls && c.rolls.length">　[{{ c.rolls.join(' + ') }}]</span>
        </div>
      </div>
    </div>
    <div class="chat-input">
      <n-input
        v-model:value="input"
        placeholder="聊天内容，或骰子表达式后点「掷骰」"
        size="small"
        :disabled="sending"
        @keyup.enter="onSend"
      />
      <div class="chat-actions">
        <n-button size="small" type="primary" :loading="sending" @click="onSend">发送</n-button>
        <n-button size="small" type="warning" :loading="sending" @click="onRoll">掷骰</n-button>
      </div>
    </div>
  </n-card>
</template>

<style scoped>
.chat-panel {
  width: 100%;
}
.chat-list {
  max-height: 220px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 10px;
  padding-right: 4px;
}
.chat-item {
  border-bottom: 1px dashed var(--border);
  padding-bottom: 6px;
}
.chat-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent-strong);
}
.chat-name.me {
  color: var(--success-color);
}
.chat-time {
  font-size: 11px;
  color: var(--text-3);
  margin-left: 6px;
}
.chat-text {
  font-size: 13px;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
}
.chat-roll {
  font-size: 13px;
  color: var(--warn-color);
  margin-top: 2px;
}
.chat-roll b {
  font-size: 15px;
}
.chat-input {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.chat-actions {
  display: flex;
  gap: 8px;
}
</style>
