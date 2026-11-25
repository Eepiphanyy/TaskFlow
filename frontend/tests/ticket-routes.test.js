import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import {
  createMemoryHistory,
  createRouter
} from 'vue-router'

import { createAuthGuard } from '../src/router/authGuard.js'
import { ticketRoutes } from '../src/router/ticketRoutes.js'
import {
  getTicketIdFromRoute,
  parseTicketIdFromRoute
} from '../src/views/tickets/ticketRoute.js'

function createTicketRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: ticketRoutes
  })
}

function unauthenticatedStore() {
  return {
    isAuthenticated: false,
    authError: null,
    initializeAuth: async () => false
  }
}

test('ticket routes match list create and detail paths', () => {
  const router = createTicketRouter()

  assert.equal(router.resolve('/tickets').name, 'ticket-list')
  assert.equal(router.resolve('/tickets/new').name, 'ticket-create')

  const detail = router.resolve('/tickets/42')
  assert.equal(detail.name, 'ticket-detail')
  assert.equal(detail.params.id, '42')
})

test('/tickets/new is ordered before the dynamic detail route', () => {
  assert.deepEqual(
    ticketRoutes.map((route) => route.path),
    ['/tickets', '/tickets/new', '/tickets/:id']
  )

  const createResolution = createTicketRouter().resolve('/tickets/new')
  assert.equal(createResolution.name, 'ticket-create')
  assert.equal(createResolution.params.id, undefined)
})

test('all ticket routes require authentication', () => {
  for (const route of ticketRoutes) {
    assert.equal(route.meta.requiresAuth, true)
  }
})

test('unauthenticated ticket navigation redirects with safe target', async () => {
  const guard = createAuthGuard(() => unauthenticatedStore())
  const resolved = createTicketRouter().resolve(
    '/tickets/42?tab=activity'
  )

  assert.deepEqual(await guard(resolved), {
    name: 'login',
    query: {
      redirect: '/tickets/42?tab=activity'
    }
  })
})

test('existing auth routes remain registered', () => {
  const routerSource = readFileSync(
    new URL('../src/router/index.js', import.meta.url),
    'utf8'
  )

  assert.match(routerSource, /alias: '\/dashboard'/)
  assert.match(routerSource, /path: '\/login'/)
  assert.match(routerSource, /path: '\/register'/)
  assert.match(routerSource, /\.\.\.ticketRoutes/)
})

test('ticket route helper reads scalar and array route ids', () => {
  assert.equal(
    getTicketIdFromRoute({ params: { id: '42' } }),
    '42'
  )
  assert.equal(
    getTicketIdFromRoute({ params: { id: ['7', '8'] } }),
    '7'
  )
  assert.equal(getTicketIdFromRoute({ params: {} }), '')
})

test('ticket route parser accepts only positive numeric ids', () => {
  assert.equal(
    parseTicketIdFromRoute({ params: { id: '42' } }),
    '42'
  )
  assert.equal(
    parseTicketIdFromRoute({ params: { id: ['7'] } }),
    '7'
  )
  assert.equal(parseTicketIdFromRoute({ params: { id: '0' } }), null)
  assert.equal(parseTicketIdFromRoute({ params: { id: '-1' } }), null)
  assert.equal(parseTicketIdFromRoute({ params: { id: '1.5' } }), null)
  assert.equal(parseTicketIdFromRoute({ params: { id: 'abc' } }), null)
})
