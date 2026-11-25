import { computed, onMounted, ref, watch } from 'vue'

function getDetailErrorMessage(error) {
  const status = error?.status || error?.response?.status
  if (status === 404) {
    return '工单不存在或无权查看'
  }

  return error?.userMessage
    || error?.response?.data?.message
    || error?.message
    || '工单详情加载失败，请稍后重试'
}

export function createTicketDetailController({
  ticketsStore,
  router,
  route,
  parseRouteId,
  registerOnMounted = onMounted,
  registerRouteWatch = watch
}) {
  const routeTicketId = ref(parseRouteId(route))
  const localError = ref('')
  let requestSequence = 0

  const currentTicket = computed(() => ticketsStore.currentTicket)
  const isDetailLoading = computed(
    () => ticketsStore.isDetailLoading
  )
  const error = computed(() => localError.value || ticketsStore.error)

  async function loadTicket(ticketId = routeTicketId.value) {
    const requestId = ++requestSequence

    if (!ticketId) {
      ticketsStore.clearCurrentTicket()
      localError.value = '无效的工单编号'
      return false
    }

    localError.value = ''
    try {
      const ticket = await ticketsStore.fetchTicket(ticketId)
      return requestId === requestSequence ? ticket : null
    } catch (requestError) {
      if (requestId === requestSequence) {
        localError.value = getDetailErrorMessage(requestError)
      }
      return false
    }
  }

  async function retry() {
    return loadTicket()
  }

  async function returnToList() {
    await router.push({ name: 'ticket-list' })
  }

  function handleRouteIdChange() {
    routeTicketId.value = parseRouteId(route)
    return loadTicket(routeTicketId.value)
  }

  registerOnMounted(() => loadTicket())
  registerRouteWatch(
    () => {
      const routeId = route?.params?.id
      return Array.isArray(routeId) ? routeId[0] || '' : routeId || ''
    },
    handleRouteIdChange
  )

  return {
    ticketId: routeTicketId,
    currentTicket,
    isDetailLoading,
    error,
    loadTicket,
    retry,
    returnToList,
    handleRouteIdChange
  }
}
