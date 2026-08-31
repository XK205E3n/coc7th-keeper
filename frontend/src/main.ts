import { createApp } from 'vue'
import { createPinia } from 'pinia'
import naive from 'naive-ui'
import './style.css'
import App from './App.vue'
import { router } from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
// naive-ui 全量注册：组件样式由 cssr 运行时注入，无需额外引入样式文件
app.use(naive)

app.mount('#app')
