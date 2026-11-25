const ACCESS_TOKEN_KEY = 'taskflow_access_token'
const REFRESH_TOKEN_KEY = 'taskflow_refresh_token'

function getSessionStorage() {
  try {
    return globalThis.sessionStorage ?? null
  } catch {
    return null
  }
}

function normalizeToken(token) {
  if (typeof token !== 'string') {
    return null
  }

  const normalized = token.trim()
  return normalized || null
}

function readToken(key) {
  const storage = getSessionStorage()

  if (!storage) {
    return null
  }

  try {
    return normalizeToken(storage.getItem(key))
  } catch {
    return null
  }
}

export function getAccessToken() {
  return readToken(ACCESS_TOKEN_KEY)
}

export function getRefreshToken() {
  return readToken(REFRESH_TOKEN_KEY)
}

export function setTokens(access, refresh) {
  const storage = getSessionStorage()
  const accessToken = normalizeToken(access)
  const refreshToken = normalizeToken(refresh)

  if (!storage || !accessToken || !refreshToken) {
    return false
  }

  try {
    storage.setItem(ACCESS_TOKEN_KEY, accessToken)
    storage.setItem(REFRESH_TOKEN_KEY, refreshToken)
    return true
  } catch {
    try {
      storage.removeItem(ACCESS_TOKEN_KEY)
      storage.removeItem(REFRESH_TOKEN_KEY)
    } catch {
      // Storage may be unavailable; callers still receive false.
    }
    return false
  }
}

export function clearTokens() {
  const storage = getSessionStorage()

  if (!storage) {
    return false
  }

  try {
    storage.removeItem(ACCESS_TOKEN_KEY)
    storage.removeItem(REFRESH_TOKEN_KEY)
    return true
  } catch {
    return false
  }
}
