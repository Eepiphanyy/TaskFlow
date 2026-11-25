<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getHealth } from '../api/health'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const loading = ref(false)
const apiStatus = ref('正在检测后端...')
const serverTime = ref('-')
const authStore = useAuthStore()
const router = useRouter()

async function checkBackend() {
  loading.value = true
  try {
    const response = await getHealth()
    apiStatus.value = response.data.message
    serverTime.value = response.data.data.timestamp
    ElMessage.success('前后端连接成功')
  } catch (error) {
    apiStatus.value = '连接失败，请确认 Django 服务已启动'
    ElMessage.error('无法连接后端接口')
    console.error(error)
  } finally {
    loading.value = false
  }
}

onMounted(checkBackend)

async function handleLogout() {
  const result = await authStore.logout()

  if (result.ignored) {
    return
  }

  if (result.serverRevoked) {
    ElMessage.success(result.message)
  } else {
    ElMessage.warning(result.message)
  }

  await router.replace({ name: 'login' })
}
</script>

<template>
  <el-container class="page">
    <el-header class="header">
      <div class="brand">TaskFlow</div>
      <div class="subtitle">企业工单与任务协作平台</div>
      <div class="user-area">
        <div class="user-avatar">
          {{ authStore.user?.username?.charAt(0)?.toUpperCase() || 'U' }}
        </div>
        <div class="user-copy">
          <strong>{{ authStore.user?.username }}</strong>
          <span>{{ authStore.user?.email }}</span>
        </div>
        <el-button
          plain
          :loading="authStore.isLoggingOut"
          @click="handleLogout"
        >
          退出登录
        </el-button>
      </div>
    </el-header>

    <el-main class="main">
      <el-card class="welcome">
        <h1>项目初始化成功</h1>
        <p>这是 TaskFlow 第一阶段的前后端联调页面。</p>
        <el-tag type="success">Vue 3 已运行</el-tag>
        <el-tag type="info" class="tag">Django API 检测</el-tag>
        <el-divider />
        <div class="status-row">
          <span>后端状态：</span>
          <strong>{{ apiStatus }}</strong>
        </div>
        <div class="status-row">
          <span>服务端时间：</span>
          <span>{{ serverTime }}</span>
        </div>
        <el-button type="primary" :loading="loading" @click="checkBackend">
          重新检测后端
        </el-button>
        <router-link
          :to="{ name: 'ticket-list' }"
          class="ticket-entry"
        >
          <el-button type="primary">进入工单列表</el-button>
        </router-link>
      </el-card>
    </el-main>
  </el-container>
</template>

<style scoped>
.page { min-height: 100vh; background: #f4f6fa; }
.header { display: flex; align-items: center; gap: 18px; background: #18243a; color: white; }
.brand { font-size: 22px; font-weight: 700; }
.subtitle { color: #c5cede; }
.user-area { display: flex; align-items: center; gap: 12px; margin-left: auto; }
.user-avatar { width: 36px; height: 36px; display: grid; place-items: center; border-radius: 50%; background: #f0f5fb; color: #1d3557; font-weight: 700; }
.user-copy { display: grid; line-height: 1.35; }
.user-copy span { color: #c5cede; font-size: 12px; }
.main { display: flex; justify-content: center; padding-top: 64px; }
.welcome { width: min(680px, 100%); }
.welcome h1 { margin-top: 0; color: #1f2937; }
.welcome p { color: #667085; }
.tag { margin-left: 8px; }
.status-row { display: flex; gap: 12px; margin: 14px 0; color: #475467; }
.ticket-entry { display: inline-block; margin-left: 10px; }
@media (max-width: 640px) {
  .header { height: auto; padding-top: 14px; padding-bottom: 14px; flex-wrap: wrap; }
  .subtitle { display: none; }
  .user-area { width: 100%; margin-left: 0; }
  .user-copy { flex: 1; }
  .main { padding-top: 28px; }
}
</style>
