import { useAuthStore } from '../stores/auth.js'

export function getSafeRedirectPath(target) {
  if (
    typeof target !== 'string'
    || !target.startsWith('/')
    || target.startsWith('//')
    || target.startsWith('/login')
  ) {
    return null
  }

  return target
}

export function createAuthGuard(getAuthStore = useAuthStore) {
  return async (to) => {
    const authStore = getAuthStore()
    await authStore.initializeAuth()

    if (to.name === 'login' || to.meta.guestOnly) {
      return authStore.isAuthenticated
        ? { name: 'dashboard' }
        : true
    }

    if (!to.meta.requiresAuth || authStore.isAuthenticated) {
      return true
    }

    const query = {
      redirect: to.fullPath
    }

    if (authStore.authError?.type) {
      query.reason = authStore.authError.type
    }

    return {
      name: 'login',
      query
    }
  }
}
