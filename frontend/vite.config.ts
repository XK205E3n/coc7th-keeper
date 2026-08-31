import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      // 开发期将 /api 代理到后端 FastAPI（uvicorn, 18000）
      '/api': 'http://localhost:18000',
    },
  },
})
