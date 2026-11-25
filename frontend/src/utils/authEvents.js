let sessionExpiredHandler = null
let tokensRefreshedHandler = null
let expirationNotificationPromise = null

export function setAuthSessionExpiredHandler(handler) {
  sessionExpiredHandler = handler

  return () => {
    if (sessionExpiredHandler === handler) {
      sessionExpiredHandler = null
    }
  }
}

export function setAuthTokensRefreshedHandler(handler) {
  tokensRefreshedHandler = handler

  return () => {
    if (tokensRefreshedHandler === handler) {
      tokensRefreshedHandler = null
    }
  }
}

export async function notifyAuthSessionExpired(reason = 'expired') {
  if (expirationNotificationPromise) {
    return expirationNotificationPromise
  }

  if (!sessionExpiredHandler) {
    return
  }

  expirationNotificationPromise = Promise.resolve(
    sessionExpiredHandler({ reason })
  ).finally(() => {
    expirationNotificationPromise = null
  })

  return expirationNotificationPromise
}

export function notifyAuthTokensRefreshed(tokens) {
  tokensRefreshedHandler?.(tokens)
}
