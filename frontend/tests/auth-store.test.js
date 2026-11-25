import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import { createPinia } from 'pinia'

class MemoryStorage {
  constructor() {
    this.values = new Map()
    this.failWrites = false
  }

  get length() {
    return this.values.size
  }

  getItem(key) {
    return this.values.has(key) ? this.values.get(key) : null
  }

  setItem(key, value) {
    if (this.failWrites) {
      throw new Error('Storage write failed')
    }

    this.values.set(key, String(value))
  }

  removeItem(key) {
    this.values.delete(key)
  }

  clear() {
    this.values.clear()
    this.failWrites = false
  }
}

const storage = new MemoryStorage()
globalThis.sessionStorage = storage

const { default: request } = await import('../src/utils/request.js')
const { refreshClient } = await import('../src/utils/authRefresh.js')
const { setTokens } = await import('../src/utils/token.js')
const { useAuthStore } = await import('../src/stores/auth.js')

const currentUser = {
  id: 7,
  username: 'current_user',
  email: 'current_user@example.com',
  permissions: [
    'tickets.process_ticket',
    'tickets.view_ticket'
  ]
}

let requestHandler
let requestCount

function createStore() {
  return useAuthStore(createPinia())
}

function successResponse(config) {
  return {
    data: {
      code: 200,
      message: '获取当前用户成功',
      data: currentUser
    },
    status: 200,
    statusText: 'OK',
    headers: {},
    config,
    request: {}
  }
}

beforeEach(() => {
  storage.clear()
  requestCount = 0
  requestHandler = async (config) => successResponse(config)
  request.defaults.adapter = async (config) => {
    requestCount += 1
    return requestHandler(config)
  }
  refreshClient.defaults.adapter = async (config) => {
    const error = new Error('Invalid refresh token')
    error.config = config
    error.response = {
      status: 401,
      data: {
        code: 401,
        message: 'Refresh Token invalid'
      }
    }
    throw error
  }
})

test('auth store starts with an empty authentication state', () => {
  const store = createStore()

  assert.equal(store.accessToken, null)
  assert.equal(store.refreshToken, null)
  assert.equal(store.user, null)
  assert.equal(store.isAuthenticated, false)
  assert.equal(store.isLoading, false)
})

test('setAuth stores tokens and current user', () => {
  const store = createStore()

  assert.equal(
    store.setAuth('access-value', 'refresh-value', currentUser),
    true
  )
  assert.equal(store.accessToken, 'access-value')
  assert.equal(store.refreshToken, 'refresh-value')
  assert.deepEqual(store.user, currentUser)
  assert.equal(store.isAuthenticated, true)
})

test('setAuth stays logged out when token storage fails', () => {
  const store = createStore()
  storage.failWrites = true

  assert.equal(
    store.setAuth('access-value', 'refresh-value', currentUser),
    false
  )
  assert.equal(store.accessToken, null)
  assert.equal(store.refreshToken, null)
  assert.equal(store.user, null)
  assert.equal(store.isAuthenticated, false)
})

test('clearAuth removes tokens and all authentication state', () => {
  const store = createStore()
  store.setAuth('access-value', 'refresh-value', currentUser)

  store.clearAuth()

  assert.equal(store.accessToken, null)
  assert.equal(store.refreshToken, null)
  assert.equal(store.user, null)
  assert.equal(store.isAuthenticated, false)
  assert.equal(storage.length, 0)
})

test('fetchCurrentUser updates the user on success', async () => {
  const store = createStore()
  setTokens('access-value', 'refresh-value')

  const user = await store.fetchCurrentUser()

  assert.deepEqual(user, currentUser)
  assert.deepEqual(store.user, currentUser)
  assert.equal(store.isAuthenticated, true)
  assert.equal(store.isLoading, false)
})

test('fetchCurrentUser normalizes missing permissions to an empty list', async () => {
  const store = createStore()
  setTokens('access-value', 'refresh-value')
  requestHandler = async (config) => ({
    ...successResponse(config),
    data: {
      code: 200,
      message: '获取当前用户成功',
      data: {
        ...currentUser,
        permissions: null
      }
    }
  })

  await store.fetchCurrentUser()

  assert.deepEqual(store.user.permissions, [])
})

test('fetchCurrentUser clears the user and restores loading on failure', async () => {
  const store = createStore()
  setTokens('access-value', 'refresh-value')
  requestHandler = async () => {
    const error = new Error('Unauthorized')
    error.response = {
      status: 401,
      data: {
        code: 401,
        message: '身份认证失败'
      }
    }
    throw error
  }

  await assert.rejects(store.fetchCurrentUser())
  assert.equal(store.user, null)
  assert.equal(store.isAuthenticated, false)
  assert.equal(store.isLoading, false)
  assert.equal(store.authError.type, 'unauthorized')
  assert.equal(storage.length, 0)
})

test('403 keeps tokens but does not report authenticated', async () => {
  const store = createStore()
  setTokens('access-value', 'refresh-value')
  requestHandler = async () => {
    const error = new Error('Forbidden')
    error.response = {
      status: 403,
      data: {
        code: 403,
        message: '权限不足'
      }
    }
    throw error
  }

  await assert.rejects(store.fetchCurrentUser())

  assert.equal(store.isAuthenticated, false)
  assert.equal(store.authError.type, 'forbidden')
  assert.equal(storage.length, 2)
})

test('network errors keep tokens and mark auth as unavailable', async () => {
  const store = createStore()
  setTokens('access-value', 'refresh-value')
  requestHandler = async () => {
    throw new Error('Network Error')
  }

  await assert.rejects(store.fetchCurrentUser())

  assert.equal(store.isAuthenticated, false)
  assert.equal(store.authError.type, 'unavailable')
  assert.equal(storage.length, 2)
})

test('500 errors keep tokens and mark auth as unavailable', async () => {
  const store = createStore()
  setTokens('access-value', 'refresh-value')
  requestHandler = async () => {
    const error = new Error('Server Error')
    error.response = {
      status: 500,
      data: {
        code: 500,
        message: '服务器内部错误'
      }
    }
    throw error
  }

  await assert.rejects(store.fetchCurrentUser())

  assert.equal(store.isAuthenticated, false)
  assert.equal(store.authError.type, 'unavailable')
  assert.equal(storage.length, 2)
})

test('initializeAuth does not request without an access token', async () => {
  const store = createStore()

  const result = await store.initializeAuth()

  assert.equal(result, false)
  assert.equal(requestCount, 0)
  assert.equal(store.isAuthenticated, false)
})

test('initializeAuth validates the current user when a token exists', async () => {
  const store = createStore()
  setTokens('access-value', 'refresh-value')

  const result = await store.initializeAuth()

  assert.equal(result, true)
  assert.equal(requestCount, 1)
  assert.deepEqual(store.user, currentUser)
  assert.equal(store.isAuthenticated, true)
  assert.equal(store.isLoading, false)
})

test('initializeAuth does not retry a failed initial request', async () => {
  const store = createStore()
  setTokens('access-value', 'refresh-value')
  requestHandler = async () => {
    const error = new Error('Unauthorized')
    error.response = {
      status: 401,
      data: {
        code: 401,
        message: '身份认证失败'
      }
    }
    throw error
  }

  assert.equal(await store.initializeAuth(), false)
  assert.equal(requestCount, 1)
  assert.equal(store.isAuthenticated, false)
  assert.equal(store.isLoading, false)

  assert.equal(await store.initializeAuth(), false)
  assert.equal(requestCount, 1)
})

test('initializeAuth prevents duplicate concurrent initialization', async () => {
  const store = createStore()
  setTokens('access-value', 'refresh-value')

  const results = await Promise.all([
    store.initializeAuth(),
    store.initializeAuth()
  ])

  assert.deepEqual(results, [true, true])
  assert.equal(requestCount, 1)
})

test('isLoading is true while fetchCurrentUser is pending', async () => {
  const store = createStore()
  setTokens('access-value', 'refresh-value')

  let notifyAdapterStarted
  let resolveRequest
  const adapterStarted = new Promise((resolve) => {
    notifyAdapterStarted = resolve
  })
  requestHandler = (config) => new Promise((resolve) => {
    resolveRequest = () => resolve(successResponse(config))
    notifyAdapterStarted()
  })

  const requestPromise = store.fetchCurrentUser()
  await adapterStarted
  assert.equal(store.isLoading, true)

  resolveRequest()
  await requestPromise
  assert.equal(store.isLoading, false)
})

test('logout submits refresh token and clears all local auth state', async () => {
  const store = createStore()
  store.setAuth('access-value', 'refresh-value', currentUser)
  let submittedBody
  requestHandler = async (config) => {
    submittedBody = JSON.parse(config.data)
    return successResponse(config)
  }

  const result = await store.logout()

  assert.deepEqual(submittedBody, { refresh: 'refresh-value' })
  assert.equal(result.serverRevoked, true)
  assert.equal(store.accessToken, null)
  assert.equal(store.refreshToken, null)
  assert.equal(store.user, null)
  assert.equal(store.isAuthenticated, false)
  assert.equal(store.isLoggingOut, false)
  assert.equal(storage.length, 0)
})

test('invalid refresh token during logout still clears local auth', async () => {
  const store = createStore()
  store.setAuth('access-value', 'refresh-value', currentUser)
  requestHandler = async () => {
    const error = new Error('Invalid refresh token')
    error.response = {
      status: 401,
      data: {
        code: 401,
        message: 'Refresh Token invalid'
      }
    }
    throw error
  }

  const result = await store.logout()

  assert.equal(result.serverRevoked, false)
  assert.equal(result.message, 'Refresh Token 已失效，本地登录状态已清除')
  assert.equal(store.user, null)
  assert.equal(store.isAuthenticated, false)
  assert.equal(storage.length, 0)
})

test('network failure during logout still clears local auth', async () => {
  const store = createStore()
  store.setAuth('access-value', 'refresh-value', currentUser)
  requestHandler = async () => {
    throw new Error('Network Error')
  }

  const result = await store.logout()

  assert.equal(result.serverRevoked, false)
  assert.equal(result.unconfirmed, true)
  assert.equal(store.authError.type, 'logout-unconfirmed')
  assert.equal(store.user, null)
  assert.equal(store.isAuthenticated, false)
  assert.equal(storage.length, 0)
})

test('500 failure during logout still clears local auth', async () => {
  const store = createStore()
  store.setAuth('access-value', 'refresh-value', currentUser)
  requestHandler = async () => {
    const error = new Error('Server Error')
    error.response = {
      status: 500,
      data: {
        code: 500,
        message: 'Server Error'
      }
    }
    throw error
  }

  const result = await store.logout()

  assert.equal(result.unconfirmed, true)
  assert.equal(store.user, null)
  assert.equal(store.isAuthenticated, false)
  assert.equal(storage.length, 0)
})

test('loading prevents duplicate logout requests', async () => {
  const store = createStore()
  store.setAuth('access-value', 'refresh-value', currentUser)
  let notifyStarted
  let resolveLogout
  let requestCount = 0
  const started = new Promise((resolve) => {
    notifyStarted = resolve
  })
  requestHandler = (config) => {
    requestCount += 1
    return new Promise((resolve) => {
      resolveLogout = () => resolve(successResponse(config))
      notifyStarted()
    })
  }

  const firstLogout = store.logout()
  await started
  assert.equal(store.isLoggingOut, true)
  const secondResult = await store.logout()
  assert.deepEqual(secondResult, { ignored: true })
  assert.equal(requestCount, 1)

  resolveLogout()
  const firstResult = await firstLogout
  assert.equal(firstResult.serverRevoked, true)
  assert.equal(store.isLoggingOut, false)
})
