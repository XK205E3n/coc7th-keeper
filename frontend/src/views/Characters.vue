<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createDiscreteApi } from 'naive-ui'
import {
  buildCharacter,
  getCharacters,
  getGame,
  getModulePregens,
} from '../api/client'
import { useAuthStore } from '../stores/auth'
import CharacterSheet from '../components/CharacterSheet.vue'
import type { CharacterEntry } from '../types'

const { message } = createDiscreteApi(['message'])

const router = useRouter()
const auth = useAuthStore()

const gameKey = computed(() => auth.gameKey)
const gameName = ref('')
const moduleId = ref<string | null>(null)
const loading = ref(false)
const loadError = ref<string | null>(null)

// ---------- 预制角色 ----------
const pregens = ref<Record<string, unknown>[]>([])
const pregenLoading = ref(false)

// ---------- AI 草稿 ----------
const autoName = ref('')
const autoLoading = ref(false)

// ---------- 手动填写 ----------
const manualName = ref('')
const manualAttrs = ref<Record<string, number | null>>({
  STR: null,
  CON: null,
  SIZ: null,
  DEX: null,
  APP: null,
  INT: null,
  POW: null,
  EDU: null,
  LUK: null,
})
const manualLoading = ref(false)

// ---------- 已有角色 ----------
const characters = ref<CharacterEntry[]>([])
const myCharacter = computed<Record<string, unknown> | null>(() => {
  if (characters.value.length === 0) return null
  const mine = characters.value.find((c) => c.uid === auth.playerUid)
  return (mine ?? characters.value[0]).data
})
const showRebuild = ref(false)

const activeTab = ref('pregen')

onMounted(async () => {
  if (!gameKey.value) return
  loading.value = true
  try {
    const view = await getGame(gameKey.value)
    gameName.value = view.game.name
    moduleId.value = view.game.module_id
    await loadCharacters()
    if (moduleId.value) await loadPregens()
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
})

async function loadCharacters(): Promise<void> {
  if (!gameKey.value) return
  const res = await getCharacters(gameKey.value)
  characters.value = res.characters
}

async function loadPregens(): Promise<void> {
  if (!moduleId.value) return
  pregenLoading.value = true
  try {
    const res = await getModulePregens(moduleId.value)
    pregens.value = res.pregens
  } catch (e) {
    message.error(`预制角色加载失败：${e instanceof Error ? e.message : String(e)}`)
  } finally {
    pregenLoading.value = false
  }
}

function pregenName(p: Record<string, unknown>): string {
  return typeof p.name === 'string' ? p.name : '未命名'
}

function pregenCn(p: Record<string, unknown>): string {
  return typeof p.cn === 'string' ? p.cn : ''
}

function pregenOccupation(p: Record<string, unknown>): string {
  const meta = (p.meta ?? {}) as Record<string, unknown>
  return typeof meta.occupation === 'string' ? meta.occupation : ''
}

function pregenBackground(p: Record<string, unknown>): string {
  const meta = (p.meta ?? {}) as Record<string, unknown>
  return typeof meta.background === 'string' ? meta.background : ''
}

async function usePregen(pregen: Record<string, unknown>): Promise<void> {
  if (!gameKey.value) return
  try {
    const name = pregenName(pregen)
    await buildCharacter(gameKey.value, { character: pregen, name })
    message.success(`已使用预制角色「${name}」`)
    await loadCharacters()
    showRebuild.value = false
  } catch (e) {
    message.error(e instanceof Error ? e.message : String(e))
  }
}

async function onAuto(): Promise<void> {
  if (!gameKey.value) return
  const name = autoName.value.trim() || '调查员'
  autoLoading.value = true
  try {
    await buildCharacter(gameKey.value, { action: 'auto', name })
    message.success(`AI 已生成角色「${name}」`)
    await loadCharacters()
    showRebuild.value = false
  } catch (e) {
    message.error(e instanceof Error ? e.message : String(e))
  } finally {
    autoLoading.value = false
  }
}

async function onManual(): Promise<void> {
  if (!gameKey.value) return
  const name = manualName.value.trim()
  if (!name) {
    message.warning('请输入角色名')
    return
  }
  const attributes: Record<string, number> = {}
  for (const key of ['STR', 'CON', 'SIZ', 'DEX', 'APP', 'INT', 'POW', 'EDU', 'LUK'] as const) {
    const v = manualAttrs.value[key]
    if (v !== null && v !== undefined && v > 0) attributes[key] = v
  }
  const character = {
    schema: 'coc7-character/v1',
    name,
    attributes,
    derived: {},
    skills: {},
    inventory: [],
  }
  manualLoading.value = true
  try {
    await buildCharacter(gameKey.value, { character, name })
    message.success(`角色「${name}」已创建`)
    await loadCharacters()
    showRebuild.value = false
  } catch (e) {
    message.error(e instanceof Error ? e.message : String(e))
  } finally {
    manualLoading.value = false
  }
}
</script>

<template>
  <section class="page">
    <!-- 未加入游戏 -->
    <n-result
      v-if="!gameKey"
      status="info"
      title="尚未加入游戏"
      description="请先在总览页创建或加入游戏"
    >
      <template #footer>
        <n-button type="primary" @click="router.push('/')">前往总览</n-button>
      </template>
    </n-result>

    <template v-else>
      <div class="page-head">
        <h1>角色</h1>
        <span v-if="gameName" class="game-name">游戏：{{ gameName }}（{{ gameKey }}）</span>
      </div>

      <n-alert v-if="loadError" type="error" class="block">
        {{ loadError }}
      </n-alert>

      <n-spin :show="loading">
        <!-- 已有角色卡：直接展示 -->
        <template v-if="myCharacter && !showRebuild">
          <n-alert type="success" class="block">
            角色卡已就绪，前往
            <RouterLink :to="`/play/${gameKey}`">游玩页</RouterLink>
            开始冒险吧！
          </n-alert>
          <CharacterSheet :character="myCharacter" />
          <div class="block">
            <n-button secondary @click="showRebuild = true">重新建卡</n-button>
          </div>
        </template>

        <!-- 建卡三步 -->
        <template v-else>
          <n-tabs v-model:value="activeTab" type="line" animated>
            <!-- 1. 预制角色 -->
            <n-tab-pane name="pregen" tab="预制角色">
              <n-alert v-if="!moduleId" type="info" class="block">
                当前游戏未绑定模组，没有预制角色可用；请选择 AI 草稿或手动填写。
              </n-alert>
              <n-spin :show="pregenLoading">
                <n-empty
                  v-if="moduleId && pregens.length === 0"
                  description="该模组没有预制角色"
                />
                <n-list v-else-if="moduleId">
                  <n-list-item v-for="(p, i) in pregens" :key="i">
                    <div class="pregen-row">
                      <div class="pregen-info">
                        <div class="pregen-name">
                          {{ pregenName(p) }}
                          <span v-if="pregenCn(p)" class="pregen-cn">{{ pregenCn(p) }}</span>
                        </div>
                        <div v-if="pregenOccupation(p)" class="pregen-occ">
                          职业：{{ pregenOccupation(p) }}
                        </div>
                        <div v-if="pregenBackground(p)" class="pregen-bg">
                          {{ pregenBackground(p) }}
                        </div>
                      </div>
                      <n-button size="small" type="primary" @click="usePregen(p)">使用</n-button>
                    </div>
                  </n-list-item>
                </n-list>
              </n-spin>
            </n-tab-pane>

            <!-- 2. AI 草稿 -->
            <n-tab-pane name="auto" tab="AI 草稿">
              <div class="auto-row">
                <n-input
                  v-model:value="autoName"
                  placeholder="角色名（留空则用玩家名）"
                  :disabled="autoLoading"
                  @keyup.enter="onAuto"
                />
                <n-button type="primary" :loading="autoLoading" :disabled="autoLoading" @click="onAuto">
                  生成
                </n-button>
              </div>
              <p class="hint">由引擎按 CoC7th 规则随机生成属性与技能初始值。</p>
            </n-tab-pane>

            <!-- 3. 手动填写 -->
            <n-tab-pane name="manual" tab="手动填写">
              <n-form label-placement="top">
                <n-form-item label="角色名">
                  <n-input
                    v-model:value="manualName"
                    placeholder="角色名"
                    :disabled="manualLoading"
                  />
                </n-form-item>
                <n-form-item label="九项属性（可留空）">
                  <div class="attr-grid">
                    <div v-for="key in ['STR', 'CON', 'SIZ', 'DEX', 'APP', 'INT', 'POW', 'EDU', 'LUK']" :key="key" class="attr-cell">
                      <span class="attr-label">{{ key }}</span>
                      <n-input-number
                        v-model:value="manualAttrs[key]"
                        :min="1"
                        :max="99"
                        :disabled="manualLoading"
                        size="small"
                      />
                    </div>
                  </div>
                </n-form-item>
                <n-button type="primary" :loading="manualLoading" :disabled="manualLoading" @click="onManual">
                  创建
                </n-button>
              </n-form>
            </n-tab-pane>
          </n-tabs>
        </template>
      </n-spin>
    </template>
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

.game-name {
  font-size: 13px;
  color: var(--text-3, #888);
}

.block {
  margin-bottom: 14px;
}

.pregen-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.pregen-name {
  font-weight: 600;
}

.pregen-cn {
  margin-left: 8px;
  font-weight: 400;
  color: var(--text-3, #888);
}

.pregen-occ {
  font-size: 12px;
  color: var(--text-3, #888);
  margin-top: 2px;
}

.pregen-bg {
  font-size: 12px;
  color: var(--text-2, #666);
  margin-top: 4px;
  line-height: 1.5;
}

.auto-row {
  display: flex;
  gap: 10px;
  max-width: 480px;
}

.hint {
  font-size: 12px;
  color: var(--text-3, #888);
  margin-top: 8px;
}

.attr-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
  width: 100%;
}

.attr-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.attr-label {
  font-size: 12px;
  color: var(--text-3, #888);
}
</style>
