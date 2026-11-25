import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'

const { default: request } = await import('../src/utils/request.js')
const {
  getCurrentUser,
  login,
  logout,
  register
} = await import('../src/api/auth.js')

let requests

beforeEach(() => {
  requests = []
  request.defaults.adapter = async (config) => {
    requests.push(config)
    return {
      data: {
        code: 200,
        message: 'success',
        data: {}
      },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
      request: {}
    }
  }
})

test('login sends credentials to the correct endpoint', async () => {
  const payload = {
    username: 'testuser',
    password: 'Test123456'
  }

  await login(payload)

  assert.equal(requests.length, 1)
  assert.equal(requests[0].method, 'post')
  assert.equal(requests[0].baseURL, '/api')
  assert.equal(requests[0].url, '/auth/login/')
  assert.deepEqual(JSON.parse(requests[0].data), payload)
})

test('getCurrentUser can use a bootstrap access token once', async () => {
  await getCurrentUser('bootstrap-access-token')

  assert.equal(requests[0].method, 'get')
  assert.equal(requests[0].url, '/auth/me/')
  assert.equal(
    requests[0].headers.get('Authorization'),
    'Bearer bootstrap-access-token'
  )
})

test('register sends all fields to the correct endpoint', async () => {
  const payload = {
    username: 'new_user',
    email: 'new_user@example.com',
    password: 'TaskFlow#2026',
    password_confirm: 'TaskFlow#2026'
  }

  await register(payload)

  assert.equal(requests[0].method, 'post')
  assert.equal(requests[0].url, '/auth/register/')
  assert.deepEqual(JSON.parse(requests[0].data), payload)
})

test('logout sends the refresh token to the correct endpoint', async () => {
  await logout({ refresh: 'refresh-value' })

  assert.equal(requests[0].method, 'post')
  assert.equal(requests[0].url, '/auth/logout/')
  assert.deepEqual(JSON.parse(requests[0].data), {
    refresh: 'refresh-value'
  })
})
