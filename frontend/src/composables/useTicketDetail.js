import { useRoute, useRouter } from 'vue-router'

import { useTicketsStore } from '../stores/tickets.js'
import { parseTicketIdFromRoute } from '../views/tickets/ticketRoute.js'
import { createTicketDetailController } from './ticketDetailController.js'

export * from './ticketDetailController.js'

export function useTicketDetail({
  ticketsStore = useTicketsStore(),
  router = useRouter(),
  route = useRoute()
} = {}) {
  return createTicketDetailController({
    ticketsStore,
    router,
    route,
    parseRouteId: parseTicketIdFromRoute
  })
}
