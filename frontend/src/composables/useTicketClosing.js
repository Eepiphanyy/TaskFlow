import { ElMessage, ElMessageBox } from 'element-plus'

import { useAuthStore } from '../stores/auth.js'
import { useTicketsStore } from '../stores/tickets.js'
import { createTicketClosingController } from './ticketClosingController.js'

export * from './ticketClosingController.js'

export function useTicketClosing({
  ticketId,
  currentTicket,
  ticketsStore = useTicketsStore(),
  authStore = useAuthStore()
}) {
  async function confirmClose() {
    try {
      await ElMessageBox.confirm(
        '关闭后将不能重新打开，确认关闭该工单吗？',
        '确认关闭工单',
        {
          type: 'warning',
          confirmButtonText: '确认关闭',
          cancelButtonText: '取消'
        }
      )
      return true
    } catch {
      return false
    }
  }

  return createTicketClosingController({
    ticketsStore,
    authStore,
    ticketId,
    currentTicket,
    confirmClose,
    notifySuccess: (message) => ElMessage.success(message),
    notifyWarning: (message) => ElMessage.warning(message),
    notifyError: (message) => ElMessage.error(message)
  })
}
