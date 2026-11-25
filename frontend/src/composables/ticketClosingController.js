import { computed, ref } from 'vue'

import { hasBusinessPermission } from '../utils/businessPermissions.js'
import { canOperateTicketByRole } from './ticketProcessingController.js'

const CLOSE_PERMISSION = 'tickets.close_ticket'

export function canCloseTicket(user, ticket) {
  return (
    hasBusinessPermission(user, CLOSE_PERMISSION)
    &&
    ticket?.status === 'resolved'
    && canOperateTicketByRole(user, ticket)
  )
}

export function getClosingErrorMessage(error) {
  const status = error?.status || error?.response?.status

  if (status === 403) {
    return '无权关闭此工单'
  }
  if (status === 404) {
    return '工单不存在或无权操作'
  }
  if (status === 409) {
    return '当前工单状态不允许关闭'
  }

  return error?.userMessage
    || error?.response?.data?.message
    || error?.message
    || '工单关闭失败，请稍后重试'
}

export function createTicketClosingController({
  ticketsStore,
  authStore,
  ticketId,
  currentTicket,
  confirmClose = async () => true,
  notifySuccess = () => {},
  notifyWarning = () => {},
  notifyError = () => {}
}) {
  const isClosing = ref(false)
  const closeError = ref('')
  const closeErrorType = ref('error')
  let isConfirmationPending = false

  const canClose = computed(
    () => canCloseTicket(authStore.user, currentTicket.value)
  )

  async function refreshTicket() {
    if (!ticketId.value) {
      return false
    }

    try {
      await ticketsStore.fetchTicket(ticketId.value)
      return true
    } catch {
      closeError.value = '工单已关闭，但详情刷新失败，请重新加载'
      closeErrorType.value = 'warning'
      notifyWarning(closeError.value)
      return false
    }
  }

  async function closeCurrentTicket() {
    if (isClosing.value || isConfirmationPending) {
      return false
    }
    if (!canClose.value || !ticketId.value) {
      closeError.value = '无权关闭此工单'
      closeErrorType.value = 'error'
      notifyError(closeError.value)
      return false
    }

    isConfirmationPending = true
    let confirmed = false
    try {
      confirmed = await confirmClose()
    } catch {
      confirmed = false
    }

    if (!confirmed) {
      isConfirmationPending = false
      return false
    }
    if (!canClose.value || !ticketId.value) {
      isConfirmationPending = false
      closeError.value = '无权关闭此工单'
      closeErrorType.value = 'error'
      notifyError(closeError.value)
      return false
    }

    isClosing.value = true
    closeError.value = ''
    closeErrorType.value = 'error'

    try {
      await ticketsStore.closeTicket(ticketId.value)
      const refreshed = await refreshTicket()
      if (!refreshed) {
        return false
      }

      notifySuccess('工单已关闭')
      return true
    } catch (requestError) {
      closeError.value = getClosingErrorMessage(requestError)
      closeErrorType.value = 'error'
      notifyError(closeError.value)
      return false
    } finally {
      isClosing.value = false
      isConfirmationPending = false
    }
  }

  return {
    isClosing,
    closeError,
    closeErrorType,
    canClose,
    closeCurrentTicket
  }
}
