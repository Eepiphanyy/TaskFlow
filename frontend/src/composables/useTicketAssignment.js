import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth.js'
import { useTicketsStore } from '../stores/tickets.js'
import { createTicketAssignmentController } from './ticketAssignmentController.js'

export * from './ticketAssignmentController.js'

export function useTicketAssignment({
  ticketId,
  currentTicket,
  ticketsStore = useTicketsStore(),
  authStore = useAuthStore()
}) {
  return createTicketAssignmentController({
    ticketsStore,
    authStore,
    ticketId,
    currentTicket,
    notifySuccess: (message) => ElMessage.success(message),
    notifyError: (message) => ElMessage.error(message)
  })
}
