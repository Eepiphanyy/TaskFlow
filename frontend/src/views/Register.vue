<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { useRegister } from '../composables/useRegister.js'

const formRef = ref()
const router = useRouter()
const {
  form,
  rules,
  loading,
  errorMessage,
  handleRegister
} = useRegister({
  formRef,
  router
})

async function submitRegister() {
  const success = await handleRegister()

  if (success) {
    ElMessage.success('注册成功，请登录')
  } else if (errorMessage.value) {
    ElMessage.error(errorMessage.value)
  }
}
</script>

<template>
  <div class="register-page">
    <el-card class="register-card" shadow="never">
      <div class="brand-mark">TF</div>
      <p class="eyebrow">TASKFLOW</p>
      <h1>创建账号</h1>
      <p class="subtitle">加入企业任务与工单协作工作台</p>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        :closable="false"
        show-icon
        class="error-alert"
      />

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="submitRegister"
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

        <el-form-item label="邮箱" prop="email">
          <el-input
            v-model="form.email"
            name="email"
            type="email"
            placeholder="请输入邮箱"
            autocomplete="email"
            clearable
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            name="password"
            type="password"
            placeholder="至少 8 位"
            autocomplete="new-password"
            show-password
          />
        </el-form-item>

        <el-form-item label="确认密码" prop="password_confirm">
          <el-input
            v-model="form.password_confirm"
            name="password_confirm"
            type="password"
            placeholder="请再次输入密码"
            autocomplete="new-password"
            show-password
          />
        </el-form-item>

        <el-button
          class="register-button"
          type="primary"
          native-type="submit"
          :loading="loading"
        >
          {{ loading ? '正在注册...' : '注册' }}
        </el-button>
      </el-form>

      <p class="switch-page">
        已有账号？
        <router-link :to="{ name: 'login' }">返回登录</router-link>
      </p>
    </el-card>
  </div>
</template>

<style scoped>
.register-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 40px 20px;
  background:
    radial-gradient(circle at 15% 10%, #dce8f5 0, transparent 34%),
    #f4f6fa;
}

.register-card {
  width: min(500px, 100%);
  border: 1px solid #e6eaf0;
  border-radius: 16px;
}

.register-card :deep(.el-card__body) {
  padding: 40px;
}

.brand-mark {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  margin-bottom: 20px;
  border-radius: 12px;
  background: #1d3557;
  color: #fff;
  font-weight: 800;
}

.eyebrow {
  margin: 0 0 10px;
  color: #6b7c93;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.18em;
}

h1 {
  margin: 0;
  color: #172033;
  font-size: 30px;
}

.subtitle {
  margin: 10px 0 28px;
  color: #697386;
}

.error-alert {
  margin-bottom: 22px;
}

.register-button {
  width: 100%;
  margin-top: 6px;
}

.switch-page {
  margin: 24px 0 0;
  color: #697386;
  font-size: 14px;
  text-align: center;
}

.switch-page a {
  color: #2563a8;
  font-weight: 600;
  text-decoration: none;
}

@media (max-width: 560px) {
  .register-page {
    padding: 20px 14px;
  }

  .register-card :deep(.el-card__body) {
    padding: 28px 22px;
  }
}
</style>
