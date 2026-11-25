import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import { createPinia } from 'pinia'
import {
  createMemoryHistory,
  createRouter
} from 'vue-router'

class MemoryStorage {
  constructor() {
    this.values = new Map()
  }

  get length() {
    return this.values.size
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

const {
  createAuthGuard,
  getSafeRedirectPath
} = await import('../src/router/authGuard.js')
const { default: request } = await import('../src/utils/request.js')
const { setTokens } = await import('../src/utils/token.js')
const { useAuthStore } = await import('../src/stores/auth.js')

const protectedTarget = {
  name: 'dashboard',
  fullPath: '/',
  meta: { requiresAuth: true }
}

function createFakeStore(overrides = {}) {
  return {
    isAuthenticated: false,
    authError: null,
    initializeAuth: async () => false,
    ...overrides
  }
}

beforeEach(() => {
  storage.clear()
})

test('unauthenticated dashboard access redirects to login with target', async () => {
  const guard = createAuthGuard(() => createFakeStore())

  const result = await guard(protectedTarget)

  assert.deepEqual(result, {
    name: 'login',
    query: { redirect: '/' }
  })
})

test('valid token restores authentication before protected route continues', async () => {
  const store = createFakeStore({
    isAuthenticated: true,
    initializeAuth: async () => true
  })
  const guard = createAuthGuard(() => store)

  assert.equal(await guard(protectedTarget), true)
})

test('invalid token redirects with an unauthorized reason', async () => {
  const store = createFakeStore({
    authError: { type: 'unauthorized' }
  })
  const guard = createAuthGuard(() => store)

  const result = await guard(protectedTarget)

  assert.deepEqual(result, {
    name: 'login',
    query: {
      redirect: '/',
      reason: 'unauthorized'
    }
  })
})

test('authenticated user visiting login is redirected to dashboard', async () => {
  const store = createFakeStore({
    isAuthenticated: true,
    initializeAuth: async () => true
  })
  const guard = createAuthGuard(() => store)

  const result = await guard({
    name: 'login',
    fullPath: '/login',
    meta: {}
  })

  assert.deepEqual(result, { name: 'dashboard' })
})

test('authenticated user visiting register is redirected to dashboard', async () => {
  const store = createFakeStore({
    isAuthenticated: true,
    initializeAuth: async () => true
  })
  const guard = createAuthGuard(() => store)

  const result = await guard({
    name: 'register',
    fullPath: '/register',
    meta: { guestOnly: true }
  })

  assert.deepEqual(result, { name: 'dashboard' })
})

test('unauthenticated user can visit register', async () => {
  const guard = createAuthGuard(() => createFakeStore())

  const result = await guard({
    name: 'register',
    fullPath: '/register',
    meta: { guestOnly: true }
  })

  assert.equal(result, true)
})

test('guard preserves the full original target', async () => {
  const store = createFakeStore()
  const guard = createAuthGuard(() => store)

  const result = await guard({
    name: 'dashboard',
    fullPath: '/tickets/42?tab=comments',
    meta: { requiresAuth: true }
  })

  assert.equal(result.query.redirect, '/tickets/42?tab=comments')
})

test('guard waits for pending authentication initialization', async () => {
  let resolveInitialization
  const initialization = new Promise((resolve) => {
    resolveInitialization = resolve
  })
  const store = createFakeStore({
    initializeAuth: () => initialization
  })
  const guard = createAuthGuard(() => store)
  let settled = false

  const navigation = guard(protectedTarget).then((result) => {
    settled = true
    return result
  })
  await Promise.resolve()
  assert.equal(settled, false)

  resolveInitialization(false)
  const result = await navigation
  assert.equal(result.name, 'login')
})

test('recoverable auth errors keep tokens but redirect with a reason', async () => {
  const store = createFakeStore({
    authError: { type: 'unavailable' }
  })
  const guard = createAuthGuard(() => store)

  const result = await guard(protectedTarget)

  assert.equal(result.query.reason, 'unavailable')
})

test('guard allows public routes without redirecting', async () => {
  const guard = createAuthGuard(() => createFakeStore())

  const result = await guard({
    name: 'public',
    fullPath: '/public',
    meta: {}
  })

  assert.equal(result, true)
})

test('safe redirects reject login and external URLs', () => {
  assert.equal(getSafeRedirectPath('/login'), null)
  assert.equal(getSafeRedirectPath('//example.com'), null)
  assert.equal(getSafeRedirectPath('https://example.com'), null)
  assert.equal(getSafeRedirectPath('/tickets/1'), '/tickets/1')
})

test('real router guard does not create a redirect loop', async () => {
  const store = createFakeStore()
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/',
        name: 'dashboard',
        component: {},
        meta: { requiresAuth: true }
      },
      {
        path: '/login',
        name: 'login',
        component: {}
      }
    ]
  })
  router.beforeEach(createAuthGuard(() => store))

  await router.push('/')
  assert.equal(router.currentRoute.value.name, 'login')

  store.isAuthenticated = true
  store.initializeAuth = async () => true
  await router.push('/')
  assert.equal(router.currentRoute.value.name, 'dashboard')

  await router.push('/login')
  assert.equal(router.currentRoute.value.name, 'dashboard')
})

test('concurrent guarded navigations share one initialization request', async () => {
  const store = useAuthStore(createPinia())
  setTokens('access-value', 'refresh-value')
  let adapterStarted
  let resolveAdapter
  let requestCount = 0
  const started = new Promise((resolve) => {
    adapterStarted = resolve
  })
  request.defaults.adapter = (config) => {
    requestCount += 1
    return new Promise((resolve) => {
      resolveAdapter = () => resolve({
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
      })
      adapterStarted()
    })
  }
  const guard = createAuthGuard(() => store)

  const firstNavigation = guard(protectedTarget)
  const secondNavigation = guard({
    ...protectedTarget,
    fullPath: '/tickets/2'
  })
  await started
  assert.equal(requestCount, 1)

  resolveAdapter()
  const results = await Promise.all([
    firstNavigation,
    secondNavigation
  ])
  assert.deepEqual(results, [true, true])
  assert.equal(requestCount, 1)
})
