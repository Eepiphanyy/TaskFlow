import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  assignTicket as assignTicketRequest,
  closeTicket as closeTicketRequest,
  createTicket as createTicketRequest,
  getTicket,
  getTicketAssignees,
  getTicketCategories,
  getTickets,
  processTicket as processTicketRequest,
  updateTicket as updateTicketRequest
} from '../api/tickets.js'

function getErrorMessage(error) {
  return error?.userMessage
    || error?.response?.data?.message
    || error?.message
    || '工单操作失败，请稍后重试'
}

function readListResponse(response) {
  const data = response?.data

  if (Array.isArray(data)) {
    return {
      tickets: data,
      pagination: {
        count: data.length,
        next: null,
        previous: null
      }
    }
  }

  return {
    tickets: Array.isArray(data?.results) ? data.results : [],
    pagination: {
      count: Number(data?.count) || 0,
      next: data?.next ?? null,
      previous: data?.previous ?? null
    }
  }
}

export const useTicketsStore = defineStore('tickets', () => {
  const tickets = ref([])
  const currentTicket = ref(null)
  const categories = ref([])
  const assignees = ref([])
  const pagination = ref({
    count: 0,
    next: null,
    previous: null
  })
  const isLoading = ref(false)
  const isDetailLoading = ref(false)
  const isCategoriesLoading = ref(false)
  const isAssigneesLoading = ref(false)
  const activeMutationCount = ref(0)
  const isMutating = computed(() => activeMutationCount.value > 0)
  const error = ref('')

  let latestListRequestId = 0
  let latestDetailRequestId = 0
  let latestCategoriesRequestId = 0
  let latestAssigneesRequestId = 0

  function syncTicket(updatedTicket) {
    if (!updatedTicket || updatedTicket.id === undefined) {
      return
    }

    const index = tickets.value.findIndex(
      (ticket) => ticket.id === updatedTicket.id
    )
    if (index >= 0) {
      tickets.value[index] = updatedTicket
    }

    if (currentTicket.value?.id === updatedTicket.id) {
      currentTicket.value = updatedTicket
    }
  }

  async function runMutation(requestAction) {
    error.value = ''
    activeMutationCount.value += 1

    try {
      const response = await requestAction()
      const updatedTicket = response?.data
      if (!updatedTicket) {
        throw new Error('工单响应数据为空')
      }
      return updatedTicket
    } catch (requestError) {
      error.value = getErrorMessage(requestError)
      throw requestError
    } finally {
      activeMutationCount.value -= 1
    }
  }

  async function fetchTickets(params = {}) {
    const requestId = ++latestListRequestId
    isLoading.value = true
    error.value = ''

    try {
      const response = await getTickets(params)
      if (requestId !== latestListRequestId) {
        return null
      }

      const listState = readListResponse(response)
      tickets.value = listState.tickets
      pagination.value = listState.pagination
      return tickets.value
    } catch (requestError) {
      if (requestId === latestListRequestId) {
        error.value = getErrorMessage(requestError)
      }
      throw requestError
    } finally {
      if (requestId === latestListRequestId) {
        isLoading.value = false
      }
    }
  }

  async function fetchTicket(id) {
    const requestId = ++latestDetailRequestId
    isDetailLoading.value = true
    error.value = ''

    try {
      const response = await getTicket(id)
      if (requestId !== latestDetailRequestId) {
        return null
      }

      currentTicket.value = response?.data ?? null
      return currentTicket.value
    } catch (requestError) {
      if (requestId === latestDetailRequestId) {
        error.value = getErrorMessage(requestError)
      }
      throw requestError
    } finally {
      if (requestId === latestDetailRequestId) {
        isDetailLoading.value = false
      }
    }
  }

  async function fetchCategories() {
    const requestId = ++latestCategoriesRequestId
    isCategoriesLoading.value = true
    error.value = ''

    try {
      const response = await getTicketCategories()
      if (requestId !== latestCategoriesRequestId) {
        return null
      }

      categories.value = Array.isArray(response?.data)
        ? response.data
        : []
      return categories.value
    } catch (requestError) {
      if (requestId === latestCategoriesRequestId) {
        error.value = getErrorMessage(requestError)
      }
      throw requestError
    } finally {
      if (requestId === latestCategoriesRequestId) {
        isCategoriesLoading.value = false
      }
    }
  }

  async function fetchAssignees() {
    const requestId = ++latestAssigneesRequestId
    isAssigneesLoading.value = true
    error.value = ''

    try {
      const response = await getTicketAssignees()
      if (requestId !== latestAssigneesRequestId) {
        return null
      }

      assignees.value = Array.isArray(response?.data)
        ? response.data
        : []
      return assignees.value
    } catch (requestError) {
      if (requestId === latestAssigneesRequestId) {
        error.value = getErrorMessage(requestError)
      }
      throw requestError
    } finally {
      if (requestId === latestAssigneesRequestId) {
        isAssigneesLoading.value = false
      }
    }
  }

  async function createTicket(data) {
    const createdTicket = await runMutation(
      () => createTicketRequest(data)
    )

    // A created ticket may not belong to the current filtered/paginated list,
    // so leave list pagination untouched and expose the new record as detail.
    currentTicket.value = createdTicket
    return createdTicket
  }

  async function updateTicket(id, data) {
    const updatedTicket = await runMutation(
      () => updateTicketRequest(id, data)
    )
    syncTicket(updatedTicket)
    return updatedTicket
  }

  async function assignTicket(id, assigneeId) {
    const updatedTicket = await runMutation(
      () => assignTicketRequest(id, assigneeId)
    )
    syncTicket(updatedTicket)
    return updatedTicket
  }

  async function processTicket(id, status) {
    const updatedTicket = await runMutation(
      () => processTicketRequest(id, status)
    )
    syncTicket(updatedTicket)
    return updatedTicket
  }

  async function closeTicket(id) {
    const updatedTicket = await runMutation(
      () => closeTicketRequest(id)
    )
    syncTicket(updatedTicket)
    return updatedTicket
  }

  function clearCurrentTicket() {
    currentTicket.value = null
  }

  return {
    tickets,
    currentTicket,
    categories,
    assignees,
    pagination,
    isLoading,
    isDetailLoading,
    isCategoriesLoading,
    isAssigneesLoading,
    isMutating,
    error,
    fetchTickets,
    fetchTicket,
    fetchCategories,
    fetchAssignees,
    createTicket,
    updateTicket,
    assignTicket,
    processTicket,
    closeTicket,
    clearCurrentTicket
  }
})
