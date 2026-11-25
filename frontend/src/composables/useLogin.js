import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  getCurrentUser,
  login as loginRequest
} from '../api/auth.js'
import { useAuthStore } from '../stores/auth.js'
import { getSafeRedirectPath } from '../router/authGuard.js'

export const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

function getLoginErrorMessage(error) {
  return error?.response?.data?.message
    || error?.userMessage
    || error?.message
    || '登录失败，请稍后重试'
}

export function useLogin({
  formRef,
  authStore = useAuthStore(),
  router = useRouter(),
  loginUser = loginRequest,
  fetchCurrentUser = getCurrentUser,
  redirectPath = null
} = {}) {
  const form = reactive({
    username: '',
    password: ''
  })
  const loading = ref(false)
  const errorMessage = ref('')

  async function handleLogin() {
    if (loading.value) {
      return false
    }

    errorMessage.value = ''

    if (!formRef?.value) {
      return false
    }

    try {
      await formRef.value.validate()
    } catch {
      return false
    }

    loading.value = true

    try {
      const loginResponse = await loginUser({
        username: form.username.trim(),
        password: form.password
      })
      const tokenData = loginResponse?.data?.data

      if (!tokenData?.access || !tokenData?.refresh) {
        throw new Error('登录响应缺少 Token')
      }

      // Tokens are not persisted until /me succeeds, so pass the new access
      // token to this one bootstrap request.
      const userResponse = await fetchCurrentUser(tokenData.access)
      const currentUser = userResponse?.data?.data

      if (!currentUser) {
        throw new Error('未能获取当前用户信息')
      }

      if (!authStore.setAuth(
        tokenData.access,
        tokenData.refresh,
        currentUser
      )) {
        authStore.clearAuth()
        throw new Error('登录状态保存失败')
      }

      try {
        await router.replace(
          getSafeRedirectPath(redirectPath)
            || { name: 'dashboard' }
        )
      } catch (error) {
        authStore.clearAuth()
        throw error
      }

      form.password = ''
      return true
    } catch (error) {
      errorMessage.value = getLoginErrorMessage(error)
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    form,
    rules: loginRules,
    loading,
    errorMessage,
    handleLogin
  }
}
