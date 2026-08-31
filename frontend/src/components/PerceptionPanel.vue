<script setup lang="ts">
import { computed } from 'vue'
import type { PerceptionEntry } from '../stores/game'

const props = defineProps<{
  perceptions: PerceptionEntry[]
}>()

/** 最近 10 条（新在前） */
const recent = computed(() => props.perceptions.slice(-10).reverse())
</script>

<template>
  <n-card title="私密感知" size="small">
    <n-empty v-if="recent.length === 0" description="暂无私密感知" size="small" />
    <n-list v-else>
      <n-list-item v-for="p in recent" :key="p.id">
        <div class="perception-text">{{ p.text }}</div>
      </n-list-item>
    </n-list>
  </n-card>
</template>

<style scoped>
.perception-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text, #333);
  word-break: break-word;
}
</style>
