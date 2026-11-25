export const DEFAULT_TASKFLOW_ROLE_CODES = new Set([
  'admin',
  'department_manager',
  'employee',
  'ticket_handler'
])

export function normalizePermissionCodes(permissions) {
  if (!Array.isArray(permissions)) {
    return []
  }

  return [...new Set(
    permissions.filter(
      (permission) => typeof permission === 'string' && permission
    )
  )].sort()
}

export function hasBusinessPermission(user, permissionKey) {
  return normalizePermissionCodes(user?.permissions)
    .includes(permissionKey)
}

export function hasCustomBusinessRole(user) {
  return (user?.roles || []).some(
    (role) => (
      typeof role?.code === 'string'
      && !DEFAULT_TASKFLOW_ROLE_CODES.has(role.code)
    )
  )
}
