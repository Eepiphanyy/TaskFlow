import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth.js'
import { useTicketsStore } from '../stores/tickets.js'
import { createTicketProcessingController } from './ticketProcessingController.js'

export * from './ticketProcessingController.js'

export function useTicketProcessing({
  ticketId,
  currentTicket,
  ticketsStore = useTicketsStore(),
  authStore = useAuthStore()
}) {
  return createTicketProcessingController({
    ticketsStore,
    authStore,
    ticketId,
    currentTicket,
    notifySuccess: (message) => ElMessage.success(message),
    notifyError: (message) => ElMessage.error(message)
  })
}
