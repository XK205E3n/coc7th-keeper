<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getHealth } from '../api/client'

const status = ref<string>('检测中…')
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    const res = await getHealth()
    status.value = res.status === 'ok' ? '后端在线' : `未知状态: ${res.status}`
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
})
</script>

<template>
  <section class="page">
    <h1>总览 Overview</h1>
    <p>这里是总览页占位 —— M4 将展示在建房间、最近活动与快捷入口。</p>
    <p class="health">
      后端状态：
      <span v-if="error" class="bad">{{ error }}</span>
      <span v-else class="ok">{{ status }}</span>
    </p>
  </section>
</template>
