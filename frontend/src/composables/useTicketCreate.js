import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { useTicketsStore } from '../stores/tickets.js'
import { createTicketCreateController } from './ticketCreateController.js'

export * from './ticketCreateController.js'

export function useTicketCreate({
  ticketsStore = useTicketsStore(),
  router = useRouter()
} = {}) {
  return createTicketCreateController({
    ticketsStore,
    router,
    notifySuccess: (message) => ElMessage.success(message),
    notifyError: (message) => ElMessage.error(message)
  })
}
