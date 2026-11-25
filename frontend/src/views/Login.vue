<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { useLogin } from '../composables/useLogin.js'
import { getSafeRedirectPath } from '../router/authGuard.js'
import { useAuthStore } from '../stores/auth.js'

const formRef = ref()
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const retryLoading = ref(false)
const redirectPath = computed(() => (
  typeof route.query.redirect === 'string'
    ? route.query.redirect
    : null
))
const authErrorMessage = computed(
  () => authStore.authError?.message || ''
)
const registrationSuccess = computed(
  () => route.query.registered === '1'
)
const canRetryAuth = computed(
  () => ['unavailable', 'unknown'].includes(authStore.authError?.type)
)
const {
  form,
  rules,
  loading,
  errorMessage,
  handleLogin
} = useLogin({
  formRef,
  authStore,
  router,
  redirectPath: redirectPath.value
})

async function submitLogin() {
  const success = await handleLogin()

  if (success) {
    ElMessage.success('登录成功')
  } else if (errorMessage.value) {
    ElMessage.error(errorMessage.value)
  }
}

async function retryAuthentication() {
  retryLoading.value = true

  try {
    const success = await authStore.retryInitializeAuth()

    if (success) {
      await router.replace(
        getSafeRedirectPath(redirectPath.value)
          || { name: 'dashboard' }
      )
    }
  } finally {
    retryLoading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <section class="brand-panel">
      <div class="brand-mark">TF</div>
      <p class="eyebrow">TASKFLOW</p>
      <h1>让工单流转更清晰，让团队协作更高效。</h1>
      <p class="brand-description">
        集中管理企业任务、工单和协作进度，帮助团队快速响应并持续改进。
      </p>
      <div class="brand-lines" aria-hidden="true">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </section>

    <main class="form-panel">
      <el-card class="login-card" shadow="never">
        <div class="mobile-brand">TaskFlow</div>
        <h2>登录工作台</h2>
        <p class="subtitle">使用企业账号继续访问 TaskFlow</p>

        <el-alert
          v-if="registrationSuccess"
          title="注册成功，请使用新账号登录"
          type="success"
          :closable="false"
          show-icon
          class="error-alert"
        />

        <el-alert
          v-if="authErrorMessage"
          :title="authErrorMessage"
          type="warning"
          :closable="false"
          show-icon
          class="error-alert"
        >
          <el-button
            v-if="canRetryAuth"
            size="small"
            :loading="retryLoading"
            @click="retryAuthentication"
          >
            重试
          </el-button>
        </el-alert>

        <el-alert
          v-if="errorMessage"
          :title="errorMessage"
          type="error"
          :closable="false"
          show-icon
          class="error-alert"
          data-test="login-error"
        />

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          size="large"
          @submit.prevent="submitLogin"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              name="username"
              placeholder="请输入用户名"
              autocomplete="username"
              clearable
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              name="password"
              type="password"
              placeholder="请输入密码"
              autocomplete="current-password"
              show-password
            />
          </el-form-item>

          <el-button
            class="login-button"
            type="primary"
            native-type="submit"
            :loading="loading"
            data-test="login-button"
          >
            {{ loading ? '正在登录...' : '登录' }}
          </el-button>
        </el-form>

        <p class="security-note">
          TaskFlow 不会在浏览器中保存你的登录密码。
        </p>

        <p class="register-link">
          还没有账号？
          <router-link :to="{ name: 'register' }">立即注册</router-link>
        </p>
      </el-card>
    </main>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(360px, 1.05fr) minmax(420px, 0.95fr);
  background: #f4f6fa;
}

.brand-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
  padding: 72px clamp(42px, 7vw, 110px);
  background: linear-gradient(145deg, #132238 0%, #1d3557 62%, #26466d 100%);
  color: #fff;
}

.brand-panel::after {
  content: '';
  position: absolute;
  right: -120px;
  bottom: -160px;
  width: 420px;
  height: 420px;
  border: 1px solid rgb(255 255 255 / 14%);
  border-radius: 50%;
}

.brand-mark {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  margin-bottom: 32px;
  border-radius: 12px;
  background: #fff;
  color: #18304f;
  font-weight: 800;
  letter-spacing: -1px;
}

.eyebrow {
  margin: 0 0 18px;
  color: #9fb9d7;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.2em;
}

.brand-panel h1 {
  max-width: 620px;
  margin: 0;
  font-size: clamp(32px, 4vw, 54px);
  line-height: 1.15;
  letter-spacing: -0.03em;
}

.brand-description {
  max-width: 520px;
  margin: 28px 0 0;
  color: #c6d5e7;
  font-size: 17px;
  line-height: 1.8;
}

.brand-lines {
  display: flex;
  gap: 8px;
  margin-top: 52px;
}

.brand-lines span {
  display: block;
  width: 34px;
  height: 3px;
  border-radius: 3px;
  background: #7fa6d3;
}

.brand-lines span:first-child {
  width: 70px;
  background: #fff;
}

.form-panel {
  display: grid;
  place-items: center;
  padding: 40px 24px;
}

.login-card {
  width: min(440px, 100%);
  border: 1px solid #e6eaf0;
  border-radius: 16px;
}

.login-card :deep(.el-card__body) {
  padding: 42px;
}

.mobile-brand {
  display: none;
}

.login-card h2 {
  margin: 0;
  color: #172033;
  font-size: 28px;
  letter-spacing: -0.02em;
}

.subtitle {
  margin: 10px 0 30px;
  color: #697386;
  line-height: 1.6;
}

.error-alert {
  margin-bottom: 22px;
}

.login-button {
  width: 100%;
  margin-top: 6px;
}

.security-note {
  margin: 24px 0 0;
  color: #8a94a6;
  font-size: 13px;
  line-height: 1.6;
  text-align: center;
}

.register-link {
  margin: 10px 0 0;
  color: #697386;
  font-size: 14px;
  text-align: center;
}

.register-link a {
  color: #2563a8;
  font-weight: 600;
  text-decoration: none;
}

@media (max-width: 860px) {
  .login-page {
    display: block;
    background:
      linear-gradient(180deg, #19304d 0, #19304d 180px, #f4f6fa 180px);
  }

  .brand-panel {
    display: none;
  }

  .form-panel {
    min-height: 100vh;
    align-items: start;
    padding-top: 72px;
  }

  .mobile-brand {
    display: block;
    margin-bottom: 20px;
    color: #1d3557;
    font-size: 20px;
    font-weight: 800;
  }

  .login-card :deep(.el-card__body) {
    padding: 32px 24px;
  }
}
</style>
