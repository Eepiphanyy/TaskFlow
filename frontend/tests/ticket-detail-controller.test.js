import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'

import { createTicketDetailController } from '../src/composables/ticketDetailController.js'
import { parseTicketIdFromRoute } from '../src/views/tickets/ticketRoute.js'

let fetchCalls
let mountedCallback
let routeWatchCallback
let routerCalls
let ticketsStore

function createController(routeId = '42') {
  const route = {
    params: {
      id: routeId
    }
  }
  const controller = createTicketDetailController({
    ticketsStore,
    router: {
      push: async (location) => {
        routerCalls.push(location)
      }
    },
    route,
    parseRouteId: parseTicketIdFromRoute,
    registerOnMounted: (callback) => {
      mountedCallback = callback
    },
    registerRouteWatch: (_getter, callback) => {
      routeWatchCallback = callback
    }
  })
  return { controller, route }
}

function mockTicket(id = 42) {
  return {
    id: Number(id),
    title: `工单 ${id}`,
    description: '详情描述',
    category: null,
    status: 'pending',
    priority: 'medium',
    creator: { id: 1, username: 'creator' },
    assignee: null,
    department: { id: 2, name: '研发部' },
    created_at: '2026-11-24T10:00:00+08:00',
    updated_at: '2026-11-24T11:00:00+08:00'
  }
}

beforeEach(() => {
  fetchCalls = []
  mountedCallback = null
  routeWatchCallback = null
  routerCalls = []
  ticketsStore = {
    currentTicket: null,
    isDetailLoading: false,
    error: '',
    fetchTicket: async (id) => {
      fetchCalls.push(id)
      const ticket = mockTicket(id)
      ticketsStore.currentTicket = ticket
      return ticket
    },
    clearCurrentTicket: () => {
      ticketsStore.currentTicket = null
    }
  }
})

test('valid route id loads ticket on mount', async () => {
  const { controller } = createController('42')

  assert.equal(typeof mountedCallback, 'function')
  await mountedCallback()

  assert.deepEqual(fetchCalls, ['42'])
  assert.equal(controller.currentTicket.value.id, 42)
})

test('invalid route id does not request ticket', async () => {
  const { controller } = createController('invalid')

  await mountedCallback()

  assert.deepEqual(fetchCalls, [])
  assert.equal(controller.currentTicket.value, null)
  assert.equal(controller.error.value, '无效的工单编号')
})

test('detail failure exposes friendly error', async () => {
  ticketsStore.fetchTicket = async () => {
    const error = new Error('not found')
    error.response = { status: 404 }
    throw error
  }
  const { controller } = createController('99')

  await mountedCallback()

  assert.equal(controller.error.value, '工单不存在或无权查看')
})

test('retry loads the same ticket after a failure', async () => {
  let attempts = 0
  ticketsStore.fetchTicket = async (id) => {
    attempts += 1
    if (attempts === 1) {
      const error = new Error('server')
      error.userMessage = '服务器暂时不可用'
      throw error
    }
    const ticket = mockTicket(id)
    ticketsStore.currentTicket = ticket
    return ticket
  }
  const { controller } = createController('42')
  await mountedCallback()

  await controller.retry()

  assert.equal(attempts, 2)
  assert.equal(controller.error.value, '')
  assert.equal(controller.currentTicket.value.id, 42)
})

test('route id change loads the new ticket', async () => {
  const { controller, route } = createController('42')
  await mountedCallback()

  route.params.id = '43'
  await routeWatchCallback()

  assert.deepEqual(fetchCalls, ['42', '43'])
  assert.equal(controller.currentTicket.value.id, 43)
})

test('route change to invalid id clears current detail', async () => {
  const { controller, route } = createController('42')
  await mountedCallback()

  route.params.id = 'abc'
  await routeWatchCallback()

  assert.deepEqual(fetchCalls, ['42'])
  assert.equal(controller.currentTicket.value, null)
  assert.equal(controller.error.value, '无效的工单编号')
})

test('old detail request result cannot replace newer request result', async () => {
  const pending = new Map()
  ticketsStore.fetchTicket = (id) => new Promise((resolve) => {
    pending.set(id, resolve)
  })
  const { controller } = createController('42')

  const first = controller.loadTicket('42')
  const second = controller.loadTicket('43')
  pending.get('43')(mockTicket('43'))
  assert.equal((await second).id, 43)
  pending.get('42')(mockTicket('42'))
  assert.equal(await first, null)
  assert.equal(controller.currentTicket.value, null)
})

test('returnToList navigates back to ticket list', async () => {
  const { controller } = createController()

  await controller.returnToList()

  assert.deepEqual(routerCalls, [{ name: 'ticket-list' }])
})
