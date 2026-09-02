<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useGameStore } from '../stores/game'
import type { MessageEntry } from '../stores/game'
import DiceCard from './DiceCard.vue'
import StateChanges from './StateChanges.vue'

const props = defineProps<{
  messages: MessageEntry[]
}>()

const gameStore = useGameStore()

// ---------- T-C3 阅读模式：点击叙事放大阅读 ----------
const readerOpen = ref(false)
const readerTitle = ref('')
const readerText = ref('')
const closeBtnRef = ref<{ $el?: HTMLElement } | null>(null)
const readerPanelRef = ref<HTMLElement | null>(null)
const prevFocus = ref<HTMLElement | null>(null)

function openReader(text: string, title: string): void {
  if (!text) return
  prevFocus.value = (document.activeElement as HTMLElement) ?? null
  readerText.value = text
  readerTitle.value = title
  readerOpen.value = true
  document.body.style.overflow = 'hidden'
  nextTick(() => {
    const el = closeBtnRef.value as unknown as { $el?: HTMLElement } | null
    el?.$el?.focus()
  })
}
function closeReader(): void {
  if (!readerOpen.value) return
  readerOpen.value = false
  document.body.style.overflow = ''
  prevFocus.value?.focus()
  prevFocus.value = null
}
function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && readerOpen.value) {
    closeReader()
  }
}
/** T-A10 Tab 焦点陷阱：模态内循环焦点，避免 Tab 跑出遮罩外的页面元素 */
function onPanelKeydown(e: KeyboardEvent): void {
  if (!readerOpen.value || e.key !== 'Tab') return
  const panel = readerPanelRef.value
  if (!panel) return
  const focusables = panel.querySelectorAll<HTMLElement>(
    'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])',
  )
  if (focusables.length === 0) {
    e.preventDefault()
    return
  }
  const first = focusables[0]
  const last = focusables[focusables.length - 1]
  const active = document.activeElement as HTMLElement | null
  if (e.shiftKey) {
    if (active === first || !panel.contains(active)) {
      e.preventDefault()
      last.focus()
    }
  } else if (active === last || !panel.contains(active)) {
    e.preventDefault()
    first.focus()
  }
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})

/** 按 round 分组（升序），组内保持消息原有顺序 */
const groups = computed(() => {
  const map = new Map<number, MessageEntry[]>()
  for (const m of props.messages) {
    const list = map.get(m.round) ?? []
    list.push(m)
    map.set(m.round, list)
  }
  return [...map.entries()].sort((a, b) => a[0] - b[0])
})

function payloadOf(m: MessageEntry): Record<string, unknown> {
  return (m.payload ?? {}) as Record<string, unknown>
}

function playerName(uid: unknown): string {
  if (typeof uid !== 'string' || uid === '') return ''
  return gameStore.players.find((p) => p.uid === uid)?.name ?? uid
}

function roundTitle(roundNo: number): string {
  return roundNo <= 0 ? '开场' : `第 ${roundNo} 轮`
}

/** 附件图片加载失败的 file 集合（失败后回退为文本提示） */
const handoutFailed = ref<Set<string>>(new Set())

function handoutUrl(file: unknown): string {
  const moduleId = gameStore.game?.module_id
  if (typeof file !== 'string' || file === '' || !moduleId) return ''
  // file 是 handouts/ 下的相对路径（可能含子目录），用 encodeURI 保留斜杠
  return `/api/modules/${encodeURIComponent(moduleId)}/handouts/${encodeURI(file)}`
}

function onHandoutError(file: unknown): void {
  if (typeof file === 'string') {
    handoutFailed.value = new Set(handoutFailed.value).add(file)
  }
}
</script>

<template>
  <div class="narration-stream">
    <n-empty v-if="messages.length === 0" description="暂无叙事内容，提交行动开始冒险吧" />
    <n-card
      v-for="[roundNo, list] in groups"
      :key="roundNo"
      class="round-card"
      :title="roundTitle(roundNo)"
      size="small"
    >
      <div v-for="m in list" :key="m.id" class="round-item">
        <!-- 场景 / 开场 -->
        <n-alert
          v-if="m.kind === 'scene'"
          type="info"
          :bordered="false"
          class="scene-block clickable"
          @click="openReader(payloadOf(m).text as string, '场景 · 开场')"
        >
          <div class="pre-wrap">{{ payloadOf(m).text }}</div>
        </n-alert>

        <!-- 判定卡片 -->
        <DiceCard
          v-else-if="m.kind === 'dice'"
          :payload="payloadOf(m)"
          :player-name="playerName(payloadOf(m).player_uid ?? payloadOf(m).uid)"
        />

        <!-- 叙事 -->
        <div
          v-else-if="m.kind === 'narration'"
          class="narration-text pre-wrap clickable"
          @click="openReader(payloadOf(m).text as string, roundTitle(m.round))"
        >
          {{ payloadOf(m).text }}
        </div>

        <!-- 系统提示（如 LLM 输出被截断，请求房主调高上限） -->
        <n-alert
          v-else-if="m.kind === 'system'"
          type="warning"
          :bordered="false"
          class="system-block clickable"
          @click="openReader(payloadOf(m).text as string, '系统提示')"
        >
          <div class="pre-wrap">{{ payloadOf(m).text }}</div>
        </n-alert>

        <!-- 状态变动 -->
        <StateChanges v-else-if="m.kind === 'state_changed'" :payload="payloadOf(m)" />

        <!-- 附件：优先渲染图片，加载失败回退为文本提示 -->
        <div v-else-if="m.kind === 'handout'" class="handout-block">
          <template
            v-if="handoutUrl(payloadOf(m).file) && !handoutFailed.has(String(payloadOf(m).file))"
          >
            <img
              :src="handoutUrl(payloadOf(m).file)"
              class="handout-img"
              :alt="`附件：${String(payloadOf(m).file)}`"
              @error="onHandoutError(payloadOf(m).file)"
            />
          </template>
          <div v-else class="handout-text">附件：{{ payloadOf(m).file }}</div>
        </div>

        <!-- 未知 kind 兜底 -->
        <pre v-else class="raw-payload">{{ JSON.stringify(payloadOf(m), null, 2) }}</pre>
      </div>
    </n-card>
  </div>

  <!-- T-C3 阅读模式：全屏遮罩 + 放大字体，右栏/页面其余内容自然被隐藏 -->
  <Teleport to="body">
    <div v-if="readerOpen" class="reader-mask" @click.self="closeReader">
      <div
        ref="readerPanelRef"
        class="reader-panel"
        role="dialog"
        aria-modal="true"
        aria-label="叙事阅读"
        @keydown="onPanelKeydown"
      >
        <div class="reader-head">
          <span class="reader-title">{{ readerTitle }}</span>
          <n-button ref="closeBtnRef" size="tiny" text @click="closeReader">✕ 关闭（Esc）</n-button>
        </div>
        <div class="reader-body">{{ readerText }}</div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.narration-stream {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.round-card {
  width: 100%;
}

.round-item {
  margin-bottom: 10px;
}

.round-item:last-child {
  margin-bottom: 0;
}

.scene-block {
  margin-bottom: 4px;
}

.narration-text {
  line-height: 1.7;
  color: var(--text, #333);
}

.system-block {
  margin-bottom: 4px;
}

.handout-block {
  padding: 4px 0;
}

.handout-img {
  max-width: 100%;
  border-radius: 6px;
  display: block;
}

.handout-text {
  font-size: 13px;
  color: var(--text-3, #888);
  padding: 4px 0;
}

.raw-payload {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-3, #888);
}

.pre-wrap {
  white-space: pre-wrap;
  word-break: break-word;
}

/* T-C3 阅读模式 */
.clickable {
  cursor: pointer;
}

.narration-text.clickable:hover {
  text-decoration: underline;
  text-decoration-color: var(--accent, #a78bfa);
}

.reader-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.reader-panel {
  background: var(--bg-card, #1a1720);
  border: 1px solid var(--border, #332d3e);
  border-radius: 10px;
  max-width: 760px;
  width: 100%;
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
}

.reader-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--border, #332d3e);
}

.reader-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text, #333);
}

.reader-body {
  padding: 18px 20px;
  overflow-y: auto;
  font-size: 1.2em;
  line-height: 1.8;
  color: var(--text, #333);
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
