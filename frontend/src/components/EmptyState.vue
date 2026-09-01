<script setup lang="ts">
/**
 * 统一空状态组件（T-B2）：图标 + 文案 + 主引导动作 三件套。
 * - description：空态文案
 * - actionLabel：主操作文案；缺省不渲染按钮
 * - to：传入则按钮为路由跳转链接；未传则点击后 emit('action')
 */
defineProps<{
  description?: string
  actionLabel?: string
  to?: string
}>()

const emit = defineEmits<{ (e: 'action'): void }>()

function onClick(): void {
  emit('action')
}
</script>

<template>
  <div class="empty-state">
    <n-empty :description="description || '暂无内容'" size="small">
      <template #extra>
        <n-button v-if="to" type="primary" size="small" @click="$router.push(to)">
          {{ actionLabel }}
        </n-button>
        <n-button v-else-if="actionLabel" type="primary" size="small" @click="onClick">
          {{ actionLabel }}
        </n-button>
      </template>
    </n-empty>
  </div>
</template>

<style scoped>
.empty-state {
  padding: 20px 12px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
</style>
