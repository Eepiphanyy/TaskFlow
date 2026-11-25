export const ticketRoutes = [
  {
    path: '/tickets',
    name: 'ticket-list',
    component: () => import('../views/tickets/TicketList.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/tickets/new',
    name: 'ticket-create',
    component: () => import('../views/tickets/TicketCreate.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/tickets/:id',
    name: 'ticket-detail',
    component: () => import('../views/tickets/TicketDetail.vue'),
    meta: { requiresAuth: true }
  }
]
