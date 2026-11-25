export function getTicketIdFromRoute(route) {
  const routeId = route?.params?.id
  return Array.isArray(routeId) ? routeId[0] || '' : routeId || ''
}

export function parseTicketIdFromRoute(route) {
  const routeId = getTicketIdFromRoute(route)
  const normalizedId = String(routeId)

  if (!/^[1-9]\d*$/.test(normalizedId)) {
    return null
  }

  return normalizedId
}
