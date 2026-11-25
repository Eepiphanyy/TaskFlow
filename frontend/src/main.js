import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import {
  setAuthSessionExpiredHandler,
  setAuthTokensRefreshedHandler
} from './utils/authEvents.js'
import { useAuthStore } from './stores/auth.js'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

const authStore = useAuthStore(pinia)

setAuthTokensRefreshedHandler(() => {
  authStore.syncTokensFromStorage()
})

setAuthSessionExpiredHandler(async () => {
  const wasInitializing = authStore.isInitializing
  authStore.clearAuth()

  if (wasInitializing || router.currentRoute.value.name === 'login') {
    return
  }

  const currentPath = router.currentRoute.value.fullPath
  await router.replace({
    name: 'login',
    query: {
      redirect: currentPath,
      reason: 'expired'
    }
  })
})

app.use(ElementPlus)
app.use(router)
app.mount('#app')
