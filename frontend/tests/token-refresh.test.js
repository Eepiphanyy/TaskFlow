import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import { createPinia } from 'pinia'

class MemoryStorage {
  constructor() {
    this.values = new Map()
  }

  getItem(key) {
    return this.values.has(key) ? this.values.get(key) : null
  }

  setItem(key, value) {
    this.values.set(key, String(value))
  }

  removeItem(key) {
    this.values.delete(key)
  }

  clear() {
    this.values.clear()
  }
}

const storage = new MemoryStorage()
globalThis.sessionStorage = storage

const { default: request } = await import('../src/utils/request.js')
const { refreshClient } = await import('../src/utils/authRefresh.js')
const {
  setAuthSessionExpiredHandler,
  setAuthTokensRefreshedHandler
} = await import('../src/utils/authEvents.js')
const {
  getAccessToken,
  getRefreshToken,
  setTokens
} = await import('../src/utils/token.js')
const { useAuthStore } = await import('../src/stores/auth.js')

let expiredEvents
let refreshedEvents

function unauthorized(config, message = 'Access Token expired') {
  const error = new Error(message)
  error.config = config
  error.response = {
    status: 401,
    data: {
      code: 401,
      message
    }
  }
  return error
}

function refreshSuccess(config, access = 'new-access', refresh = 'new-refresh') {
  return {
    data: {
      code: 200,
      message: 'Token 刷新成功',
      data: { access, refresh }
    },
    status: 200,
    statusText: 'OK',
    headers: {},
    config,
    request: {}
  }
}

function success(config) {
  return {
    data: {
      code: 200,
      data: {
        id: 1,
        username: 'testuser',
        email: 'testuser@example.com'
      }
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
  expiredEvents = []
  refreshedEvents = []
  setAuthSessionExpiredHandler(async (event) => {
    expiredEvents.push(event)
  })
  setAuthTokensRefreshedHandler((tokens) => {
    refreshedEvents.push(tokens)
  })
  request.defaults.adapter = async (config) => success(config)
  refreshClient.defaults.adapter = async (config) => refreshSuccess(config)
})

test('valid access token does not trigger refresh', async () => {
  setTokens('old-access', 'old-refresh')
  let refreshCount = 0
  refreshClient.defaults.adapter = async (config) => {
    refreshCount += 1
    return refreshSuccess(config)
  }

  const response = await request.get('/protected/')

  assert.equal(response.status, 200)
  assert.equal(refreshCount, 0)
  assert.equal(getAccessToken(), 'old-access')
  assert.equal(getRefreshToken(), 'old-refresh')
})

test('401 refreshes tokens and retries the original request', async () => {
  setTokens('old-access', 'old-refresh')
  let businessCalls = 0
  request.defaults.adapter = async (config) => {
    businessCalls += 1

    if (businessCalls === 1) {
      throw unauthorized(config)
    }

    assert.equal(
      config.headers.get('Authorization'),
      'Bearer new-access'
    )
    return success(config)
  }
  let refreshCount = 0
  refreshClient.defaults.adapter = async (config) => {
    refreshCount += 1
    assert.deepEqual(JSON.parse(config.data), {
      refresh: 'old-refresh'
    })
    return refreshSuccess(config)
  }

  const response = await request.get('/protected/')

  assert.equal(response.status, 200)
  assert.equal(businessCalls, 2)
  assert.equal(refreshCount, 1)
  assert.equal(getAccessToken(), 'new-access')
  assert.equal(getRefreshToken(), 'new-refresh')
  assert.deepEqual(refreshedEvents, [{
    access: 'new-access',
    refresh: 'new-refresh'
  }])
})

test('refresh failure clears both tokens and emits session expiry once', async () => {
  setTokens('old-access', 'old-refresh')
  request.defaults.adapter = async (config) => {
    throw unauthorized(config)
  }
  refreshClient.defaults.adapter = async (config) => {
    throw unauthorized(config, 'Refresh Token expired')
  }

  await assert.rejects(request.get('/protected/'))

  assert.equal(getAccessToken(), null)
  assert.equal(getRefreshToken(), null)
  assert.equal(expiredEvents.length, 1)
})

test('missing refresh token clears session without requesting refresh', async () => {
  setTokens('old-access', 'old-refresh')
  storage.removeItem('taskflow_refresh_token')
  request.defaults.adapter = async (config) => {
    throw unauthorized(config)
  }
  let refreshCount = 0
  refreshClient.defaults.adapter = async (config) => {
    refreshCount += 1
    return refreshSuccess(config)
  }

  await assert.rejects(request.get('/protected/'))

  assert.equal(refreshCount, 0)
  assert.equal(getAccessToken(), null)
  assert.equal(expiredEvents.length, 1)
})

test('retry is attempted at most once', async () => {
  setTokens('old-access', 'old-refresh')
  let businessCalls = 0
  let refreshCount = 0
  request.defaults.adapter = async (config) => {
    businessCalls += 1
    throw unauthorized(config)
  }
  refreshClient.defaults.adapter = async (config) => {
    refreshCount += 1
    return refreshSuccess(config)
  }

  await assert.rejects(request.get('/protected/'))

  assert.equal(businessCalls, 2)
  assert.equal(refreshCount, 1)
  assert.equal(expiredEvents.length, 1)
})

test('login 401 does not trigger refresh', async () => {
  let refreshCount = 0
  request.defaults.adapter = async (config) => {
    throw unauthorized(config)
  }
  refreshClient.defaults.adapter = async (config) => {
    refreshCount += 1
    return refreshSuccess(config)
  }

  await assert.rejects(
    request.post('/auth/login/', {
      username: 'testuser',
      password: 'wrong'
    })
  )

  assert.equal(refreshCount, 0)
})

test('refresh endpoint 401 cannot trigger secondary refresh', async () => {
  let refreshCount = 0
  request.defaults.adapter = async (config) => {
    throw unauthorized(config)
  }
  refreshClient.defaults.adapter = async (config) => {
    refreshCount += 1
    return refreshSuccess(config)
  }

  await assert.rejects(
    request.post('/auth/token/refresh/', { refresh: 'bad' })
  )

  assert.equal(refreshCount, 0)
})

test('403 does not trigger refresh', async () => {
  setTokens('old-access', 'old-refresh')
  let refreshCount = 0
  request.defaults.adapter = async (config) => {
    const error = new Error('Forbidden')
    error.config = config
    error.response = {
      status: 403,
      data: { code: 403, message: 'Forbidden' }
    }
    throw error
  }
  refreshClient.defaults.adapter = async (config) => {
    refreshCount += 1
    return refreshSuccess(config)
  }

  await assert.rejects(request.get('/protected/'))

  assert.equal(refreshCount, 0)
  assert.equal(getAccessToken(), 'old-access')
})

async function assertRefreshInfrastructureErrorPreservesTokens(refreshError) {
  setTokens('old-access', 'old-refresh')
  request.defaults.adapter = async (config) => {
    throw unauthorized(config)
  }
  refreshClient.defaults.adapter = async () => {
    throw refreshError
  }

  await assert.rejects(request.get('/protected/'))

  assert.equal(getAccessToken(), 'old-access')
  assert.equal(getRefreshToken(), 'old-refresh')
  assert.equal(expiredEvents.length, 0)
}

test('refresh network errors preserve tokens', async () => {
  await assertRefreshInfrastructureErrorPreservesTokens(
    new Error('Network Error')
  )
})

test('refresh 500 errors preserve tokens', async () => {
  const error = new Error('Server Error')
  error.response = {
    status: 500,
    data: { code: 500, message: 'Server Error' }
  }
  await assertRefreshInfrastructureErrorPreservesTokens(error)
})

test('three concurrent 401 responses share one refresh request', async () => {
  setTokens('old-access', 'old-refresh')
  let businessCalls = 0
  request.defaults.adapter = async (config) => {
    businessCalls += 1

    if (config.headers.get('Authorization') === 'Bearer old-access') {
      throw unauthorized(config)
    }

    return success(config)
  }
  let refreshCount = 0
  let startRefresh
  let resolveRefresh
  const refreshStarted = new Promise((resolve) => {
    startRefresh = resolve
  })
  refreshClient.defaults.adapter = (config) => {
    refreshCount += 1
    return new Promise((resolve) => {
      resolveRefresh = () => resolve(refreshSuccess(config))
      startRefresh()
    })
  }

  const requests = [
    request.get('/protected/a/'),
    request.get('/protected/b/'),
    request.get('/protected/c/')
  ]
  await refreshStarted
  assert.equal(refreshCount, 1)
  assert.equal(businessCalls, 3)

  resolveRefresh()
  const responses = await Promise.all(requests)

  assert.equal(refreshCount, 1)
  assert.equal(businessCalls, 6)
  assert.deepEqual(
    responses.map((response) => response.status),
    [200, 200, 200]
  )
  assert.equal(getAccessToken(), 'new-access')
  assert.equal(getRefreshToken(), 'new-refresh')
})

test('late 401 response retries with a token refreshed by another request', async () => {
  setTokens('old-access', 'old-refresh')
  let requestACalls = 0
  let requestBCalls = 0
  let rejectRequestB
  let notifyRequestBStarted
  const requestBStarted = new Promise((resolve) => {
    notifyRequestBStarted = resolve
  })
  request.defaults.adapter = async (config) => {
    const authorization = config.headers.get('Authorization')

    if (config.url === '/protected/a/') {
      requestACalls += 1

      if (authorization === 'Bearer old-access') {
        throw unauthorized(config)
      }

      return success(config)
    }

    requestBCalls += 1

    if (authorization === 'Bearer old-access') {
      return new Promise((resolve, reject) => {
        rejectRequestB = () => reject(unauthorized(config))
        notifyRequestBStarted()
      })
    }

    return success(config)
  }

  let refreshCount = 0
  let resolveRefresh
  let notifyRefreshStarted
  const refreshStarted = new Promise((resolve) => {
    notifyRefreshStarted = resolve
  })
  refreshClient.defaults.adapter = (config) => {
    refreshCount += 1
    return new Promise((resolve) => {
      resolveRefresh = () => resolve(refreshSuccess(config))
      notifyRefreshStarted()
    })
  }

  const requestA = request.get('/protected/a/')
  await refreshStarted
  const requestB = request.get('/protected/b/')
  await requestBStarted

  resolveRefresh()
  const responseA = await requestA
  rejectRequestB()
  const responseB = await requestB

  assert.equal(responseA.status, 200)
  assert.equal(responseB.status, 200)
  assert.equal(requestACalls, 2)
  assert.equal(requestBCalls, 2)
  assert.equal(refreshCount, 1)
  assert.equal(getAccessToken(), 'new-access')
  assert.equal(getRefreshToken(), 'new-refresh')
  assert.equal(expiredEvents.length, 0)
})

test('late 401 retry with changed token is allowed only once', async () => {
  setTokens('old-access', 'old-refresh')
  let requestACalls = 0
  let requestBCalls = 0
  let resolveRequestB
  let notifyRequestBStarted
  const requestBStarted = new Promise((resolve) => {
    notifyRequestBStarted = resolve
  })
  request.defaults.adapter = async (config) => {
    const authorization = config.headers.get('Authorization')

    if (config.url === '/protected/a/') {
      requestACalls += 1

      if (authorization === 'Bearer old-access') {
        throw unauthorized(config)
      }

      return success(config)
    }

    requestBCalls += 1

    if (authorization === 'Bearer old-access') {
      return new Promise((resolve, reject) => {
        resolveRequestB = () => reject(unauthorized(config))
        notifyRequestBStarted()
      })
    }

    throw unauthorized(config, 'New access token rejected')
  }

  let refreshCount = 0
  let resolveRefresh
  let notifyRefreshStarted
  const refreshStarted = new Promise((resolve) => {
    notifyRefreshStarted = resolve
  })
  refreshClient.defaults.adapter = (config) => {
    refreshCount += 1
    return new Promise((resolve) => {
      resolveRefresh = () => resolve(refreshSuccess(config))
      notifyRefreshStarted()
    })
  }

  const requestA = request.get('/protected/a/')
  await refreshStarted
  const requestB = request.get('/protected/b/')
  await requestBStarted

  resolveRefresh()
  await requestA
  resolveRequestB()
  await assert.rejects(requestB)

  assert.equal(requestACalls, 2)
  assert.equal(requestBCalls, 2)
  assert.equal(refreshCount, 1)
  assert.equal(expiredEvents.length, 1)
})

test('concurrent refresh failure clears auth once for all requests', async () => {
  setTokens('old-access', 'old-refresh')
  let businessCalls = 0
  let refreshCount = 0
  let resolveRefreshFailure
  let startRefresh
  request.defaults.adapter = async (config) => {
    businessCalls += 1
    throw unauthorized(config)
  }
  const refreshStarted = new Promise((resolve) => {
    startRefresh = resolve
  })
  refreshClient.defaults.adapter = (config) => {
    refreshCount += 1
    return new Promise((resolve, reject) => {
      resolveRefreshFailure = () => reject(
        unauthorized(config, 'Refresh Token is blacklisted')
      )
      startRefresh()
    })
  }

  const requests = [
    request.get('/protected/a/'),
    request.get('/protected/b/'),
    request.get('/protected/c/')
  ]
  await refreshStarted
  resolveRefreshFailure()
  const results = await Promise.allSettled(requests)

  assert.equal(results.every((result) => result.status === 'rejected'), true)
  assert.equal(refreshCount, 1)
  assert.equal(businessCalls, 3)
  assert.equal(expiredEvents.length, 1)
  assert.equal(getAccessToken(), null)
  assert.equal(getRefreshToken(), null)
})

test('initialization recovers when access is expired and refresh is valid', async () => {
  const store = useAuthStore(createPinia())
  setTokens('old-access', 'old-refresh')
  request.defaults.adapter = async (config) => {
    if (config.headers.get('Authorization') === 'Bearer old-access') {
      throw unauthorized(config)
    }
    return success(config)
  }
  refreshClient.defaults.adapter = async (config) => refreshSuccess(config)

  const result = await store.initializeAuth()

  assert.equal(result, true)
  assert.equal(store.user.username, 'testuser')
  assert.equal(store.isAuthenticated, true)
  assert.equal(getAccessToken(), 'new-access')
  assert.equal(getRefreshToken(), 'new-refresh')
})

test('initialization logs out when both tokens are invalid', async () => {
  const store = useAuthStore(createPinia())
  setTokens('old-access', 'old-refresh')
  request.defaults.adapter = async (config) => {
    throw unauthorized(config)
  }
  refreshClient.defaults.adapter = async (config) => {
    throw unauthorized(config, 'Refresh Token invalid')
  }

  const result = await store.initializeAuth()

  assert.equal(result, false)
  assert.equal(store.isAuthenticated, false)
  assert.equal(getAccessToken(), null)
  assert.equal(getRefreshToken(), null)
  assert.equal(expiredEvents.length, 1)
})
