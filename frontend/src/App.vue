<script setup>
import { useAuthStore } from './stores/auth.js'

const authStore = useAuthStore()
</script>

<template>
  <div v-if="authStore.isInitializing" class="auth-loading">
    <div class="loading-mark">TF</div>
    <p>正在确认登录状态...</p>
  </div>
  <router-view v-else />
</template>

<style>
html,
body,
#app {
  min-height: 100%;
  margin: 0;
}

body {
  font-family:
    Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
}

.auth-loading {
  min-height: 100vh;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 14px;
  background: #f4f6fa;
  color: #64748b;
}

.loading-mark {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: #1d3557;
  color: #fff;
  font-weight: 800;
}

.auth-loading p {
  margin: 0;
  font-size: 14px;
}
</style>
