import axios from 'axios'

import {
  notifyAuthSessionExpired,
  notifyAuthTokensRefreshed
} from './authEvents.js'
import {
  clearTokens,
  getRefreshToken,
  setTokens
} from './token.js'

export const refreshClient = axios.create({
  baseURL: import.meta.env?.VITE_API_BASE_URL || '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

let refreshPromise = null

function createSessionError(message) {
  const error = new Error(message)
  error.response = {
    status: 401,
    data: {
      code: 401,
      message
    }
  }
  error.sessionExpired = true
  return error
}

export async function expireAuthSession(error) {
  clearTokens()

  try {
    await notifyAuthSessionExpired('expired')
  } catch {
    // Authentication state is already cleared even if navigation fails.
  }

  error.sessionExpired = true
  return error
}

async function performRefresh() {
  const currentRefreshToken = getRefreshToken()

  if (!currentRefreshToken) {
    throw await expireAuthSession(
      createSessionError('Refresh Token 不存在，请重新登录')
    )
  }

  let response

  try {
    response = await refreshClient.post(
      '/auth/token/refresh/',
      { refresh: currentRefreshToken }
    )
  } catch (error) {
    const status = error.response?.status

    if (status === 400 || status === 401) {
      throw await expireAuthSession(error)
    }

    throw error
  }

  const tokenData = response?.data?.data

  if (
    !tokenData?.access
    || !tokenData?.refresh
    || !setTokens(tokenData.access, tokenData.refresh)
  ) {
    throw await expireAuthSession(
      createSessionError('Token 刷新成功，但新 Token 无法保存')
    )
  }

  notifyAuthTokensRefreshed(tokenData)
  return tokenData
}

export function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => {
      refreshPromise = null
    })
  }

  return refreshPromise
}
