import { computed, ref } from 'vue'

import {
  hasBusinessPermission,
  hasCustomBusinessRole
} from '../utils/businessPermissions.js'

const ADMIN_ROLE_CODE = 'admin'
const DEPARTMENT_MANAGER_ROLE_CODE = 'department_manager'
const TICKET_HANDLER_ROLE_CODE = 'ticket_handler'
const PROCESS_PERMISSION = 'tickets.process_ticket'

const PROCESS_ACTIONS = {
  pending: {
    targetStatus: 'processing',
    label: '开始处理',
    successMessage: '工单已开始处理'
  },
  processing: {
    targetStatus: 'resolved',
    label: '标记解决',
    successMessage: '工单已标记解决'
  }
}

export function getTicketProcessingAction(ticket) {
  return PROCESS_ACTIONS[ticket?.status] || null
}

export function canOperateTicketByRole(user, ticket) {
  const roleCodes = new Set(
    (user?.roles || []).map((role) => role.code)
  )
  if (roleCodes.has(ADMIN_ROLE_CODE)) {
    return true
  }

  if (
    roleCodes.has(DEPARTMENT_MANAGER_ROLE_CODE)
    && user?.department?.id != null
    && ticket.department?.id === user.department.id
  ) {
    return true
  }

  if (
    roleCodes.has(TICKET_HANDLER_ROLE_CODE)
    && user?.id != null
    && ticket.assignee?.id === user.id
  ) {
    return true
  }

  return hasCustomBusinessRole(user)
}

export function canProcessTicket(user, ticket) {
  return (
    hasBusinessPermission(user, PROCESS_PERMISSION)
    &&
    Boolean(getTicketProcessingAction(ticket))
    && canOperateTicketByRole(user, ticket)
  )
}

export function getProcessingErrorMessage(error) {
  const status = error?.status || error?.response?.status

  if (status === 403) {
    return '无权处理此工单'
  }
  if (status === 404) {
    return '工单不存在或无权处理'
  }
  if (status === 409) {
    return '当前工单状态不允许该处理操作'
  }

  return error?.userMessage
    || error?.response?.data?.message
    || error?.message
    || '工单处理失败，请稍后重试'
}

export function createTicketProcessingController({
  ticketsStore,
  authStore,
  ticketId,
  currentTicket,
  notifySuccess = () => {},
  notifyError = () => {}
}) {
  const isProcessing = ref(false)
  const processError = ref('')

  const availableAction = computed(
    () => getTicketProcessingAction(currentTicket.value)
  )
  const canProcess = computed(
    () => canProcessTicket(authStore.user, currentTicket.value)
  )
  const processActionLabel = computed(
    () => (canProcess.value ? availableAction.value?.label : '')
  )

  async function refreshTicket() {
    if (!ticketId.value) {
      return false
    }

    try {
      await ticketsStore.fetchTicket(ticketId.value)
      return true
    } catch {
      processError.value = '工单状态已更新，但详情刷新失败'
      notifyError(processError.value)
      return false
    }
  }

  async function processCurrentTicket() {
    if (isProcessing.value) {
      return false
    }

    const action = availableAction.value
    if (!canProcess.value || !ticketId.value || !action) {
      processError.value = '无权处理此工单'
      notifyError(processError.value)
      return false
    }

    isProcessing.value = true
    processError.value = ''

    try {
      await ticketsStore.processTicket(
        ticketId.value,
        action.targetStatus
      )
      const refreshed = await refreshTicket()
      if (!refreshed) {
        return false
      }

      notifySuccess(action.successMessage)
      return true
    } catch (requestError) {
      processError.value = getProcessingErrorMessage(requestError)
      notifyError(processError.value)
      return false
    } finally {
      isProcessing.value = false
    }
  }

  return {
    isProcessing,
    processError,
    canProcess,
    processActionLabel,
    processCurrentTicket
  }
}
