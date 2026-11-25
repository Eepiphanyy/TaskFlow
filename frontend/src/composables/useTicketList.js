import { useRouter } from 'vue-router'

import { useTicketsStore } from '../stores/tickets.js'
import { createTicketListController } from './ticketListController.js'

export * from './ticketListController.js'

export function useTicketList({
  ticketsStore = useTicketsStore(),
  router = useRouter()
} = {}) {
  return createTicketListController({
    ticketsStore,
    router
  })
}
