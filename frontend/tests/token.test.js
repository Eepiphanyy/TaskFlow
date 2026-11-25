import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'

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
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens
} = await import('../src/utils/token.js')
const { default: request } = await import('../src/utils/request.js')

request.defaults.adapter = async (config) => ({
  data: {},
  status: 200,
  statusText: 'OK',
  headers: {},
  config,
  request: {}
})

function getHeader(headers, name) {
  if (typeof headers?.get === 'function') {
    return headers.get(name)
  }

  return headers?.[name]
}

beforeEach(() => {
  storage.clear()
})

test('initial token values are empty', () => {
  assert.equal(getAccessToken(), null)
  assert.equal(getRefreshToken(), null)
})

test('setTokens saves both token values', () => {
  assert.equal(setTokens('access-value', 'refresh-value'), true)
  assert.equal(getAccessToken(), 'access-value')
  assert.equal(getRefreshToken(), 'refresh-value')
  assert.equal(storage.length, 2)
})

test('access and refresh tokens use separate storage entries', () => {
  setTokens('access-value', 'refresh-value')

  assert.notEqual(storage.getItem('taskflow_access_token'), storage.getItem('taskflow_refresh_token'))
  assert.equal(storage.getItem('taskflow_access_token'), 'access-value')
  assert.equal(storage.getItem('taskflow_refresh_token'), 'refresh-value')
})

test('clearTokens removes both token values', () => {
  setTokens('access-value', 'refresh-value')

  assert.equal(clearTokens(), true)
  assert.equal(getAccessToken(), null)
  assert.equal(getRefreshToken(), null)
  assert.equal(storage.length, 0)
})

test('setTokens does not partially save empty values', () => {
  assert.equal(setTokens('', 'refresh-value'), false)
  assert.equal(getAccessToken(), null)
  assert.equal(getRefreshToken(), null)
})

test('Axios adds the access token as a Bearer header', async () => {
  setTokens('access-value', 'refresh-value')

  const response = await request.get('/health/')

  assert.equal(
    getHeader(response.config.headers, 'Authorization'),
    'Bearer access-value'
  )
})

test('Axios does not add Authorization without an access token', async () => {
  const response = await request.get('/health/')

  assert.equal(getHeader(response.config.headers, 'Authorization'), undefined)
})

test('Axios never sends the refresh token in business request headers', async () => {
  setTokens('access-value', 'refresh-value')

  const response = await request.get('/health/')
  const serializedHeaders = JSON.stringify(response.config.headers.toJSON())

  assert.equal(
    getHeader(response.config.headers, 'Authorization'),
    'Bearer access-value'
  )
  assert.equal(serializedHeaders.includes('refresh-value'), false)
})
