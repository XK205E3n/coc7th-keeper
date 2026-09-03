<script setup lang="ts">
/**
 * M8R5 进站门禁：服务端启用 access_password 后，未认证会话先输密码。
 * 密码校验通过后服务端下发 cookie，此后 API/SSE 自动携带，无需前端逐请求带凭据。
 * access_password 未设置（required=false）时本组件直接放行，行为与旧版一致。
 */
import { onMounted, ref } from 'vue'
import { accessCheck, accessLogin } from '../api/client'

const emit = defineEmits<{ (e: 'ready'): void }>()

const checking = ref(true)
const required = ref(false)
const password = ref('')
const busy = ref(false)
const error = ref('')

function release(): void {
  checking.value = false
  required.value = false
  emit('ready')
}

onMounted(async () => {
  try {
    const res = await accessCheck()
    required.value = res.required
    if (!res.required || res.authenticated) {
      release()
      return
    }
    checking.value = false
  } catch {
    // 门禁探测失败（后端未启动等）不拦页面 —— 让各视图自己的错误处理接管
    release()
  }
})

async function onSubmit(): Promise<void> {
  if (!password.value.trim()) return
  busy.value = true
  error.value = ''
  try {
    const res = await accessLogin(password.value)
    if (res.authenticated) {
      release()
      return
    }
    error.value = '访问密码错误'
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="checking" class="gate-loading">加载中…</div>
  <div v-else class="gate-mask">
    <div class="gate-card">
      <h2 class="gate-title">🕯 CoC 跑团平台</h2>
      <p class="gate-desc">本站已启用访问密码，请输入后进入。</p>
      <n-input
        v-model:value="password"
        type="password"
        show-password-on="click"
        placeholder="访问密码"
        :disabled="busy"
        @keyup.enter="onSubmit"
      />
      <n-button type="primary" block :loading="busy" @click="onSubmit">进入</n-button>
      <div v-if="error" class="gate-error">{{ error }}</div>
    </div>
  </div>
</template>

<style scoped>
.gate-loading {
  padding: 40px;
  text-align: center;
  color: #9d94ad;
}
.gate-mask {
  min-height: 70vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.gate-card {
  width: min(360px, 92vw);
  background: #1a1720;
  border: 1px solid #332d3e;
  border-radius: 10px;
  padding: 26px 22px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.gate-title {
  margin: 0;
  font-size: 18px;
  color: #efeaf6;
  text-align: center;
}
.gate-desc {
  margin: 0;
  font-size: 13px;
  color: #9d94ad;
  text-align: center;
}
.gate-error {
  font-size: 13px;
  color: #f87171;
  text-align: center;
}
</style>
