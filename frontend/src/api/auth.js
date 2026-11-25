import request from '../utils/request.js'

export function login(data) {
  return request.post('/auth/login/', data)
}

export function register(data) {
  return request.post('/auth/register/', data)
}

export function logout(data) {
  return request.post('/auth/logout/', data)
}

export function getCurrentUser(accessToken = null) {
  const config = accessToken
    ? {
        headers: {
          Authorization: `Bearer ${accessToken}`
        }
      }
    : undefined

  return request.get('/auth/me/', config)
}
