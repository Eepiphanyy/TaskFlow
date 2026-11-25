import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'

const { useLogin } = await import('../src/composables/useLogin.js')

const currentUser = {
  id: 9,
  username: 'testuser',
  email: 'testuser@example.com'
}

let calls
let authStore
let router
let loginUser
let fetchCurrentUser

function validFormRef() {
  return {
    value: {
      validate: async () => true
    }
  }
}

function createLogin(overrides = {}) {
  return useLogin({
    formRef: overrides.formRef ?? validFormRef(),
    authStore,
    router,
    loginUser,
    fetchCurrentUser
  })
}

beforeEach(() => {
  calls = []
  authStore = {
    setAuth: (...args) => {
      calls.push(['setAuth', ...args])
      return true
    },
    clearAuth: () => {
      calls.push(['clearAuth'])
    }
  }
  router = {
    replace: async (location) => {
      calls.push(['replace', location])
    }
  }
  loginUser = async (data) => {
    calls.push(['login', data])
    return {
      data: {
        code: 200,
        data: {
          access: 'access-value',
          refresh: 'refresh-value'
        }
      }
    }
  }
  fetchCurrentUser = async (accessToken) => {
    calls.push(['fetchCurrentUser', accessToken])
    return {
      data: {
        code: 200,
        data: currentUser
      }
    }
  }
})

async function submit(loginState, credentials = {}) {
  loginState.form.username = credentials.username ?? 'testuser'
  loginState.form.password = credentials.password ?? 'Test123456'
  return loginState.handleLogin()
}

test('successful login fetches the user, saves auth and redirects', async () => {
  const loginState = createLogin()

  const result = await submit(loginState)

  assert.equal(result, true)
  assert.deepEqual(calls[0], [
    'login',
    {
      username: 'testuser',
      password: 'Test123456'
    }
  ])
  assert.deepEqual(calls[1], ['fetchCurrentUser', 'access-value'])
  assert.deepEqual(calls[2], [
    'setAuth',
    'access-value',
    'refresh-value',
    currentUser
  ])
  assert.deepEqual(calls[3], [
    'replace',
    { name: 'dashboard' }
  ])
  assert.equal(loginState.errorMessage.value, '')
  assert.equal(loginState.loading.value, false)
})

test('successful login returns to the original protected path', async () => {
  const loginState = useLogin({
    formRef: validFormRef(),
    authStore,
    router,
    loginUser,
    fetchCurrentUser,
    redirectPath: '/tickets/42?tab=comments'
  })

  const result = await submit(loginState)

  assert.equal(result, true)
  assert.deepEqual(calls.at(-1), [
    'replace',
    '/tickets/42?tab=comments'
  ])
})

test('wrong password shows the backend error and does not save auth', async () => {
  loginUser = async () => {
    const error = new Error('Unauthorized')
    error.response = {
      status: 401,
      data: {
        code: 401,
        message: '用户名或密码错误，或账号不可用。'
      }
    }
    throw error
  }
  const loginState = createLogin()

  const result = await submit(loginState, { password: 'WrongPassword' })

  assert.equal(result, false)
  assert.equal(
    loginState.errorMessage.value,
    '用户名或密码错误，或账号不可用。'
  )
  assert.equal(calls.some(([name]) => name === 'setAuth'), false)
  assert.equal(loginState.loading.value, false)
})

test('current user failure keeps the store logged out', async () => {
  fetchCurrentUser = async () => {
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
  const loginState = createLogin()

  const result = await submit(loginState)

  assert.equal(result, false)
  assert.equal(loginState.errorMessage.value, '身份认证失败')
  assert.equal(calls.some(([name]) => name === 'setAuth'), false)
  assert.equal(loginState.loading.value, false)
})

test('token storage failure clears auth and does not redirect', async () => {
  authStore.setAuth = () => {
    calls.push(['setAuthFailed'])
    return false
  }
  const loginState = createLogin()

  const result = await submit(loginState)

  assert.equal(result, false)
  assert.equal(loginState.errorMessage.value, '登录状态保存失败')
  assert.equal(calls.some(([name]) => name === 'setAuthFailed'), true)
  assert.equal(calls.some(([name]) => name === 'clearAuth'), true)
  assert.equal(calls.some(([name]) => name === 'replace'), false)
})

test('invalid form does not submit credentials', async () => {
  const invalidFormRef = {
    value: {
      validate: async () => {
        throw new Error('Validation failed')
      }
    }
  }
  const loginState = createLogin({ formRef: invalidFormRef })

  const result = await submit(loginState)

  assert.equal(result, false)
  assert.equal(calls.length, 0)
  assert.equal(loginState.loading.value, false)
})

test('loading is true during the complete login flow and resets', async () => {
  let notifyLoginStarted
  let resolveLogin
  const loginStarted = new Promise((resolve) => {
    notifyLoginStarted = resolve
  })
  loginUser = (data) => {
    calls.push(['login', data])
    return new Promise((resolve) => {
      resolveLogin = () => resolve({
        data: {
          data: {
            access: 'access-value',
            refresh: 'refresh-value'
          }
        }
      })
      notifyLoginStarted()
    })
  }
  const loginState = createLogin()

  const loginPromise = submit(loginState)
  await loginStarted
  assert.equal(loginState.loading.value, true)

  resolveLogin()
  assert.equal(await loginPromise, true)
  assert.equal(loginState.loading.value, false)
})
