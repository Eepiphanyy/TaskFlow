import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth.js'
import { useTicketsStore } from '../stores/tickets.js'
import { createTicketEditingController } from './ticketEditingController.js'

export * from './ticketEditingController.js'

export function useTicketEditing({
  ticketId,
  currentTicket,
  ticketsStore = useTicketsStore(),
  authStore = useAuthStore()
}) {
  return createTicketEditingController({
    ticketsStore,
    authStore,
    ticketId,
    currentTicket,
    notifySuccess: (message) => ElMessage.success(message),
    notifyWarning: (message) => ElMessage.warning(message),
    notifyError: (message) => ElMessage.error(message)
  })
}
