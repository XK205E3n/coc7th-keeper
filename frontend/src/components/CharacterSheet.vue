<script setup lang="ts">
import { computed, ref } from 'vue'

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

// ---------- T-C1 技能搜索 + 分组 ----------
const skillQuery = ref('')

/** 技能 → 分组（中英文名关键词匹配；未命中归「其他」） */
const GROUP_KEYWORDS: { name: string; keywords: string[] }[] = [
  {
    name: '战斗',
    keywords: [
      '格斗', '斗殴', '武术', '拳', '棍棒', '刀', '射击', '手枪', '步枪', '霰弹',
      '弓', '投掷', '闪避', 'fighting', 'brawl', 'firearm', 'handgun', 'rifle',
      'shotgun', 'archery', 'throw', 'dodge', 'melee',
    ],
  },
  {
    name: '社交',
    keywords: [
      '话术', '说服', '恐吓', '信用', '魅惑', '表演', '乔装', '欺骗', '心理学',
      'psychology', 'fast talk', 'persuade', 'intimidate', 'credit rating',
      'credit', 'charm', 'disguise', 'art', 'craft',
    ],
  },
  {
    name: '学术',
    keywords: [
      '侦查', '调查', '倾听', '聆听', '图书馆', '追踪', '估价', '神秘学', '克苏鲁',
      '医学', '急救', '历史', '考古', '人类学', '化学', '生物学', '物理', '法律',
      '计算机', '电工', '电子维修', '机械', '驾驶', '攀爬', '游泳', '潜行', '藏匿',
      '锁匠', '导航', 'spot hidden', 'spot', 'listen', 'library use', 'track',
      'appraise', 'occult', 'cthulhu', 'medicine', 'first aid', 'history',
      'archaeology', 'anthropology', 'biology', 'chemistry', 'physics', 'science', 'law',
      'computer', 'repair', 'locksmith', 'drive', 'climb', 'swim', 'stealth',
      'hide', 'navigate',
    ],
  },
]

function groupOf(skill: string): string {
  const s = skill.toLowerCase()
  for (const g of GROUP_KEYWORDS) {
    if (g.keywords.some((k) => s.includes(k))) return g.name
  }
  return '其他'
}

/** 中文技能名 → 英文技能名子串（auto 卡技能为英文名，支持中文搜索） */
const CN_TO_EN: Record<string, string> = {
  急救: 'first aid', 侦查: 'spot hidden', 调查: 'spot hidden', 倾听: 'listen',
  聆听: 'listen', 图书馆: 'library', 说服: 'persuade', 话术: 'fast talk',
  恐吓: 'intimidate', 信用: 'credit', 闪避: 'dodge', 格斗: 'brawl', 斗殴: 'brawl',
  射击: 'firearm', 手枪: 'handgun', 步枪: 'rifle', 投掷: 'throw', 潜行: 'stealth',
  藏匿: 'stealth', 攀爬: 'climb', 游泳: 'swim', 驾驶: 'drive', 心理: 'psychology',
  心理学: 'psychology', 医学: 'medicine', 神秘学: 'occult', 克苏鲁: 'cthulhu', 历史: 'history',
  考古: 'archaeology', 人类学: 'anthropology', 化学: 'science', 生物: 'science',
  物理: 'science', 法律: 'law', 计算机: 'elec repair', 追踪: 'track', 估价: 'appraise',
  乔装: 'disguise', 表演: 'art', 导航: 'navigate', 锁匠: 'locksmith', 开锁: 'locksmith',
  机械: 'repair', 电工: 'elec repair', 跳: 'jump', 语言: 'language',
  自然: 'natural world', 会计: 'accounting', 骑: 'ride', 生存: 'survival',
  科学: 'science', 精神分析: 'psychoanalysis', 重型: 'op hvy machine',
  飞行员: 'pilot', 巧手: 'sleight of hand', 威吓: 'intimidate', 恐吓术: 'intimidate',
}

/** 技能是否匹配搜索词：命中英文名 / 中文名直配 / 中→英映射 */
function skillMatches(skill: string, q: string): boolean {
  const s = skill.toLowerCase()
  if (s.includes(q)) return true
  const en = CN_TO_EN[q]
  return en !== undefined && s.includes(en)
}

const GROUP_NAMES = ['战斗', '社交', '学术', '其他']

/** 某组当前（按搜索词过滤后）的技能列表；每次渲染实时计算，避开折叠组件缓存旧 DOM */
function groupItems(name: string): { skill: string; value: string }[] {
  const q = skillQuery.value.trim().toLowerCase()
  const qList: { skill: string; value: string }[] = []
  for (const s of skills.value) {
    if (q && !skillMatches(s.skill, q)) continue
    if (groupOf(s.skill) !== name) continue
    qList.push(s)
  }
  return qList
}

const expandedGroups = ref<string[]>(['战斗', '社交', '学术'])
const hasSkillMatch = computed(() => GROUP_NAMES.some((n) => groupItems(n).length > 0))

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
      <n-input
        v-model:value="skillQuery"
        size="small"
        clearable
        placeholder="搜索技能，如：急救"
        class="skill-search"
      />
      <n-collapse v-model:expanded-names="expandedGroups" class="skill-groups">
        <n-collapse-item v-for="gName in GROUP_NAMES" :key="gName" :name="gName">
          <template #header>
            <span class="skill-group-name">{{ gName }}</span>
            <span class="skill-group-count">{{ groupItems(gName).length }}</span>
          </template>
          <n-table
            v-if="groupItems(gName).length > 0"
            :bordered="false"
            size="small"
            :single-line="false"
          >
            <thead>
              <tr>
                <th>技能</th>
                <th style="width: 80px">值</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in groupItems(gName)" :key="s.skill">
                <td>{{ s.skill }}</td>
                <td>{{ s.value }}</td>
              </tr>
            </tbody>
          </n-table>
        </n-collapse-item>
      </n-collapse>
      <n-empty
        v-if="skillQuery && !hasSkillMatch"
        description="未找到匹配技能"
        size="small"
        class="skill-empty"
      />
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

.skill-search {
  margin-bottom: 10px;
}

.skill-empty {
  padding: 12px 0;
}

.skill-group-name {
  font-weight: 600;
}

.skill-group-count {
  margin-left: 8px;
  font-size: 12px;
  color: var(--text-3, #888);
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
