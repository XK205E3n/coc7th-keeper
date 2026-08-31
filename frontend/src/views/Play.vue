<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const gameKey = computed(() =>
  typeof route.params.key === 'string' ? route.params.key : '',
)
</script>

<template>
  <section class="page">
    <h1>游玩 Play</h1>
    <p>房间 <code>{{ gameKey || '（未指定）' }}</code> 占位 —— M4 将在这里实现叙事流、行动提交与骰点。</p>
  </section>
</template>
