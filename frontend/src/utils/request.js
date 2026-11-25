import axios from 'axios'

import {
  expireAuthSession,
  refreshAccessToken
} from './authRefresh.js'
import { getAccessToken } from './token.js'

const statusMessages = {
  400: '请求参数错误',
  401: '身份认证失败',
  403: '权限不足',
  404: '接口不存在',
  500: '服务器内部错误'
}

function getErrorMessage(error) {
  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
    return '请求超时，请稍后重试'
  }

  if (!error.response) {
    return '网络连接失败，请检查网络或后端服务'
  }

  return statusMessages[error.response.status]
    || `请求失败（HTTP ${error.response.status}）`
}

const authPathsWithoutRefresh = [
  '/auth/login/',
  '/auth/register/',
  '/auth/logout/',
  '/auth/token/refresh/'
]

function shouldRefresh(error) {
  const url = error.config?.url || ''

  return error.response?.status === 401
    && Boolean(error.config)
    && !error.config?._retry
    && !authPathsWithoutRefresh.some((path) => url.includes(path))
}

const request = axios.create({
  baseURL: import.meta.env?.VITE_API_BASE_URL || '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

request.interceptors.request.use(
  (config) => {
    const accessToken = getAccessToken()
    config._accessTokenUsed = accessToken || null

    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`
    }

    return config
  },
  (error) => Promise.reject(error)
)

request.interceptors.response.use(
  (response) => response,
  async (error) => {
    error.status = error.response?.status ?? null
    error.data = error.response?.data
    error.userMessage = getErrorMessage(error)

    if (shouldRefresh(error)) {
      const requestAccessToken = error.config._accessTokenUsed || null
      const currentAccessToken = getAccessToken()

      if (requestAccessToken !== currentAccessToken) {
        if (!currentAccessToken) {
          return Promise.reject(error)
        }

        error.config._retry = true
        return request(error.config)
      }

      error.config._retry = true

      try {
        await refreshAccessToken()
        return request(error.config)
      } catch (refreshError) {
        refreshError.originalError = error
        refreshError.userMessage = getErrorMessage(refreshError)
        return Promise.reject(refreshError)
      }
    }

    if (
      error.response?.status === 401
      && error.config?._retry
      && !authPathsWithoutRefresh.some(
        (path) => error.config.url?.includes(path)
      )
    ) {
      await expireAuthSession(error)
    }

    return Promise.reject(error)
  }
)

export default request
