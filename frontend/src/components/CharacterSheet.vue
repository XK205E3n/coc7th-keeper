<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  /** 角色卡 JSON（schema: coc7-character/v1） */
  character: Record<string, unknown>
}>()

const ATTR_LABELS: Record<string, string> = {
  STR: '力量',
  CON: '体质',
  SIZ: '体型',
  DEX: '敏捷',
  APP: '外貌',
  INT: '智力',
  POW: '意志',
  EDU: '教育',
  LUK: '幸运',
}

const DERIVED_LABELS: Record<string, string> = {
  HP: '生命值',
  MP: '魔法值',
  SAN: '理智值',
  DB: '伤害加值',
  MOV: '移动力',
}

const name = computed(() => String(props.character.name ?? '未命名'))
const cn = computed(() => (typeof props.character.cn === 'string' ? props.character.cn : ''))
const meta = computed(() => (props.character.meta ?? {}) as Record<string, unknown>)
const attributes = computed(() => (props.character.attributes ?? {}) as Record<string, unknown>)
const derived = computed(() => (props.character.derived ?? {}) as Record<string, unknown>)
const state = computed(() => (props.character.state ?? {}) as Record<string, unknown>)
const sanity = computed(() => (props.character.sanity ?? {}) as Record<string, unknown>)

const attributeItems = computed(() =>
  Object.entries(ATTR_LABELS).map(([key, label]) => ({
    label,
    value: attributes.value[key] !== undefined ? String(attributes.value[key]) : '—',
  })),
)

const derivedItems = computed(() =>
  Object.entries(DERIVED_LABELS).map(([key, label]) => ({
    label,
    value: derived.value[key] !== undefined ? String(derived.value[key]) : '—',
  })),
)

const stateItems = computed(() => {
  const s = state.value
  const items: { label: string; value: string }[] = []
  if (s.hp !== undefined) items.push({ label: '当前体力', value: `${String(s.hp)}/${String(s.max_hp ?? '?')}` })
  if (s.san !== undefined) items.push({ label: '当前理智', value: `${String(s.san)}/${String(s.max_san ?? '?')}` })
  if (Array.isArray(s.clues)) items.push({ label: '线索', value: String((s.clues as unknown[]).length) })
  if (Array.isArray(s.conditions) && (s.conditions as unknown[]).length > 0) {
    items.push({ label: '状态', value: (s.conditions as unknown[]).join('、') })
  }
  if (s.gold !== undefined) items.push({ label: '金钱', value: String(s.gold) })
  return items
})

const skills = computed(() => {
  const raw = props.character.skills
  if (!raw || typeof raw !== 'object') return []
  const entries = Object.entries(raw as Record<string, unknown>)
  return entries
    .map(([skill, value]) => ({ skill, value: String(value ?? '—') }))
    .sort((a, b) => Number(b.value) - Number(a.value))
})

const inventory = computed(() =>
  Array.isArray(props.character.inventory) ? (props.character.inventory as unknown[]) : [],
)

const sanityHistory = computed(() => {
  const h = sanity.value.history
  if (!Array.isArray(h)) return []
  return (h as Record<string, unknown>[]).slice(-5).reverse()
})

const occupation = computed(() => {
  const v = meta.value.occupation
  return typeof v === 'string' && v !== '' ? v : ''
})
</script>

<template>
  <n-card :title="name" size="small">
    <template v-if="cn" #header-extra>
      <n-text depth="3">{{ cn }}</n-text>
    </template>

    <div v-if="occupation" class="sheet-meta">职业：{{ occupation }}</div>

    <n-descriptions v-if="attributeItems.length > 0" title="属性" :column="3" size="small" bordered>
      <n-descriptions-item v-for="item in attributeItems" :key="item.label" :label="item.label">
        {{ item.value }}
      </n-descriptions-item>
    </n-descriptions>

    <n-descriptions v-if="derivedItems.length > 0" title="派生" :column="5" size="small" bordered class="sheet-block">
      <n-descriptions-item v-for="item in derivedItems" :key="item.label" :label="item.label">
        {{ item.value }}
      </n-descriptions-item>
    </n-descriptions>

    <n-descriptions v-if="stateItems.length > 0" title="当前状态" :column="3" size="small" bordered class="sheet-block">
      <n-descriptions-item v-for="item in stateItems" :key="item.label" :label="item.label">
        {{ item.value }}
      </n-descriptions-item>
    </n-descriptions>

    <div v-if="skills.length > 0" class="sheet-block">
      <h4 class="sheet-title">技能</h4>
      <n-table :bordered="false" size="small" :single-line="false">
        <thead>
          <tr>
            <th>技能</th>
            <th style="width: 80px">值</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in skills" :key="s.skill">
            <td>{{ s.skill }}</td>
            <td>{{ s.value }}</td>
          </tr>
        </tbody>
      </n-table>
    </div>

    <div v-if="inventory.length > 0" class="sheet-block">
      <h4 class="sheet-title">物品</h4>
      <n-list>
        <n-list-item v-for="(item, i) in inventory" :key="i">
          {{ item }}
        </n-list-item>
      </n-list>
    </div>

    <div v-if="sanityHistory.length > 0" class="sheet-block">
      <h4 class="sheet-title">理智历史（最近 5 条）</h4>
      <n-list>
        <n-list-item v-for="(h, i) in sanityHistory" :key="i">
          <span class="sanity-loss">-{{ String(h.loss ?? '?') }}</span>
          <span class="sanity-reason">{{ String(h.reason ?? '') }}</span>
        </n-list-item>
      </n-list>
    </div>
  </n-card>
</template>

<style scoped>
.sheet-meta {
  font-size: 13px;
  color: var(--text-3, #888);
  margin-bottom: 10px;
}

.sheet-block {
  margin-top: 14px;
}

.sheet-title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}

.sanity-loss {
  font-weight: 600;
  color: var(--error-color, #d03050);
  margin-right: 8px;
}

.sanity-reason {
  color: var(--text, #333);
}
</style>
