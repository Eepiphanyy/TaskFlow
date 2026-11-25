import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  getCurrentUser,
  logout as logoutRequest
} from '../api/auth.js'
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens
} from '../utils/token.js'
import { normalizePermissionCodes } from '../utils/businessPermissions.js'

function normalizeCurrentUser(currentUser) {
  if (!currentUser || typeof currentUser !== 'object') {
    return currentUser
  }

  return {
    ...currentUser,
    permissions: normalizePermissionCodes(currentUser.permissions)
  }
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(null)
  const refreshToken = ref(null)
  const user = ref(null)
  const isLoading = ref(false)
  const isInitialized = ref(false)
  const authError = ref(null)
  const isLoggingOut = ref(false)
  const isAuthenticated = computed(
    () => Boolean(accessToken.value && user.value)
  )
  const isInitializing = computed(
    () => !isInitialized.value && isLoading.value
  )

  let initializationPromise = null

  function setAuth(access, refresh, currentUser) {
    if (!setTokens(access, refresh) || !currentUser) {
      clearAuth()
      authError.value = {
        type: 'storage',
        message: '登录状态保存失败，请重试'
      }
      return false
    }

    accessToken.value = getAccessToken()
    refreshToken.value = getRefreshToken()
    user.value = normalizeCurrentUser(currentUser)
    authError.value = null
    isInitialized.value = true
    return true
  }

  function clearAuth() {
    clearTokens()
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    isLoading.value = false
    authError.value = null
    isInitialized.value = true
  }

  function createAuthError(error) {
    const status = error?.response?.status

    if (status === 401) {
      return {
        type: 'unauthorized',
        message: '登录状态已失效，请重新登录'
      }
    }

    if (status === 403) {
      return {
        type: 'forbidden',
        message: '当前账号无权访问该页面'
      }
    }

    if (!error?.response || status >= 500) {
      return {
        type: 'unavailable',
        message: '暂时无法确认登录状态，请检查网络后重试'
      }
    }

    return {
      type: 'unknown',
      message: '登录状态确认失败，请稍后重试'
    }
  }

  async function fetchCurrentUser() {
    isLoading.value = true
    authError.value = null

    try {
      const response = await getCurrentUser()
      user.value = normalizeCurrentUser(response.data.data)
      accessToken.value = getAccessToken()
      refreshToken.value = getRefreshToken()
      isInitialized.value = true
      return user.value
    } catch (error) {
      const nextError = createAuthError(error)

      if (nextError.type === 'unauthorized') {
        clearAuth()
      } else {
        user.value = null
      }

      authError.value = nextError
      isInitialized.value = true
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function initializeAuth() {
    if (isInitialized.value) {
      return isAuthenticated.value
    }

    if (initializationPromise) {
      return initializationPromise
    }

    initializationPromise = (async () => {
      accessToken.value = getAccessToken()
      refreshToken.value = getRefreshToken()

      if (!accessToken.value) {
        user.value = null
        isInitialized.value = true
        isLoading.value = false
        return false
      }

      try {
        await fetchCurrentUser()
        return isAuthenticated.value
      } catch {
        return false
      } finally {
        isInitialized.value = true
      }
    })()

    try {
      return await initializationPromise
    } finally {
      initializationPromise = null
    }
  }

  async function retryInitializeAuth() {
    authError.value = null
    isInitialized.value = false
    return initializeAuth()
  }

  function syncTokensFromStorage() {
    accessToken.value = getAccessToken()
    refreshToken.value = getRefreshToken()
  }

  async function logout() {
    if (isLoggingOut.value) {
      return {
        ignored: true
      }
    }

    isLoggingOut.value = true
    const currentRefreshToken = getRefreshToken()
    let result = {
      serverRevoked: false,
      unconfirmed: false,
      message: ''
    }

    try {
      if (!currentRefreshToken) {
        result.message = 'Refresh Token 已失效，本地登录状态已清除'
      } else {
        await logoutRequest({
          refresh: currentRefreshToken
        })
        result.serverRevoked = true
        result.message = '退出登录成功'
      }
    } catch (error) {
      const status = error?.response?.status

      if (!error?.response || status >= 500) {
        result.unconfirmed = true
        result.message = '本地已退出，但服务端撤销状态尚未确认'
      } else if (status === 400 || status === 401) {
        result.message = 'Refresh Token 已失效，本地登录状态已清除'
      } else {
        result.unconfirmed = true
        result.message = '本地已退出，服务端撤销状态尚未确认'
      }
    } finally {
      clearAuth()
      isLoggingOut.value = false

      if (result.unconfirmed) {
        authError.value = {
          type: 'logout-unconfirmed',
          message: result.message
        }
      }
    }

    return result
  }

  return {
    accessToken,
    refreshToken,
    user,
    isAuthenticated,
    isLoading,
    isInitialized,
    isInitializing,
    authError,
    isLoggingOut,
    setAuth,
    clearAuth,
    fetchCurrentUser,
    initializeAuth,
    retryInitializeAuth,
    syncTokensFromStorage,
    logout
  }
})
