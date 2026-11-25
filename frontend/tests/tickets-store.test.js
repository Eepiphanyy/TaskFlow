import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { beforeEach, test } from 'node:test'
import { createPinia } from 'pinia'

const apiNames = [
  'getTickets',
  'getTicket',
  'createTicket',
  'getTicketCategories',
  'getTicketAssignees',
  'updateTicket',
  'assignTicket',
  'processTicket',
  'closeTicket'
]

const mockApiSource = `
export const calls = []
const handlers = {}

function call(name, args) {
  calls.push({ name, args })
  if (!handlers[name]) {
    throw new Error(\`Missing mock handler for \${name}\`)
  }
  return handlers[name](...args)
}

export function setMockHandler(name, handler) {
  handlers[name] = handler
}

export function resetMockApi() {
  calls.length = 0
  for (const name of Object.keys(handlers)) {
    delete handlers[name]
  }
}

${apiNames.map((name) => (
  `export function ${name}(...args) { return call('${name}', args) }`
)).join('\n')}
`

const mockApiUrl = `data:text/javascript;base64,${
  Buffer.from(mockApiSource).toString('base64')
}`
const storeSourceUrl = new URL('../src/stores/tickets.js', import.meta.url)
const storeSource = readFileSync(storeSourceUrl, 'utf8')
  .replace(
    "from 'vue'",
    `from '${import.meta.resolve('vue')}'`
  )
  .replace(
    "from 'pinia'",
    `from '${import.meta.resolve('pinia')}'`
  )
  .replace(
    "from '../api/tickets.js'",
    `from '${mockApiUrl}'`
  )
const storeModuleUrl = `data:text/javascript;base64,${
  Buffer.from(storeSource).toString('base64')
}`

const mockApi = await import(mockApiUrl)
const { useTicketsStore } = await import(storeModuleUrl)

const ticket = {
  id: 12,
  title: '网络中断',
  description: '办公网络无法访问',
  status: 'pending',
  priority: 'medium',
  assignee: null
}

function createStore() {
  return useTicketsStore(createPinia())
}

function success(data) {
  return Promise.resolve({ data })
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

beforeEach(() => {
  mockApi.resetMockApi()
  mockApi.setMockHandler('getTickets', () => success({
    count: 0,
    next: null,
    previous: null,
    results: []
  }))
  mockApi.setMockHandler('getTicket', () => success(ticket))
  mockApi.setMockHandler('createTicket', () => success(ticket))
  mockApi.setMockHandler('updateTicket', () => success(ticket))
  mockApi.setMockHandler('getTicketCategories', () => success([]))
  mockApi.setMockHandler('getTicketAssignees', () => success([]))
  mockApi.setMockHandler('assignTicket', () => success(ticket))
  mockApi.setMockHandler('processTicket', () => success(ticket))
  mockApi.setMockHandler('closeTicket', () => success(ticket))
})

test('tickets store starts with an empty state', () => {
  const store = createStore()

  assert.deepEqual(store.tickets, [])
  assert.equal(store.currentTicket, null)
  assert.deepEqual(store.categories, [])
  assert.deepEqual(store.assignees, [])
  assert.deepEqual(store.pagination, {
    count: 0,
    next: null,
    previous: null
  })
  assert.equal(store.isLoading, false)
  assert.equal(store.isDetailLoading, false)
  assert.equal(store.isCategoriesLoading, false)
  assert.equal(store.isAssigneesLoading, false)
  assert.equal(store.isMutating, false)
  assert.equal(store.error, '')
})

test('fetchTickets stores results and pagination', async () => {
  const store = createStore()
  mockApi.setMockHandler('getTickets', (params) => {
    assert.deepEqual(params, { page: 2, search: '网络' })
    return success({
      count: 7,
      next: 'http://example.test/?page=3',
      previous: 'http://example.test/?page=1',
      results: [ticket]
    })
  })

  await store.fetchTickets({ page: 2, search: '网络' })

  assert.deepEqual(store.tickets, [ticket])
  assert.deepEqual(store.pagination, {
    count: 7,
    next: 'http://example.test/?page=3',
    previous: 'http://example.test/?page=1'
  })
  assert.equal(store.isLoading, false)
  assert.equal(store.error, '')
})

test('fetchTickets exposes errors and resets loading', async () => {
  const store = createStore()
  const apiError = new Error('failed')
  apiError.userMessage = '无法加载工单列表'
  mockApi.setMockHandler('getTickets', () => Promise.reject(apiError))

  await assert.rejects(store.fetchTickets())

  assert.equal(store.error, '无法加载工单列表')
  assert.equal(store.isLoading, false)
})

test('fetchTicket stores current ticket detail', async () => {
  const store = createStore()

  await store.fetchTicket(12)

  assert.deepEqual(mockApi.calls.at(-1), {
    name: 'getTicket',
    args: [12]
  })
  assert.deepEqual(store.currentTicket, ticket)
  assert.equal(store.isDetailLoading, false)
})

test('fetchCategories stores category data', async () => {
  const store = createStore()
  const categories = [
    { id: 1, name: '网络问题', description: '访问异常' }
  ]
  mockApi.setMockHandler(
    'getTicketCategories',
    () => success(categories)
  )

  await store.fetchCategories()

  assert.deepEqual(store.categories, categories)
  assert.equal(store.isCategoriesLoading, false)
})

test('fetchAssignees stores candidate data', async () => {
  const store = createStore()
  const assignees = [
    {
      id: 8,
      username: 'handler',
      department: { id: 2, name: '研发部' }
    }
  ]
  mockApi.setMockHandler(
    'getTicketAssignees',
    () => success(assignees)
  )

  await store.fetchAssignees()

  assert.deepEqual(store.assignees, assignees)
  assert.equal(store.isAssigneesLoading, false)
})

test('fetchAssignees exposes errors and restores loading', async () => {
  const store = createStore()
  const apiError = new Error('candidate failed')
  apiError.userMessage = '无法加载处理人'
  mockApi.setMockHandler(
    'getTicketAssignees',
    () => Promise.reject(apiError)
  )

  await assert.rejects(store.fetchAssignees())

  assert.equal(store.error, '无法加载处理人')
  assert.equal(store.isAssigneesLoading, false)
})

test('createTicket exposes the new ticket as current detail', async () => {
  const store = createStore()
  store.tickets = [ticket]
  store.pagination = {
    count: 1,
    next: null,
    previous: null
  }
  const payload = {
    title: '新工单',
    description: '新工单描述',
    category: 1
  }
  const created = {
    ...ticket,
    id: 21,
    title: payload.title,
    description: payload.description
  }
  mockApi.setMockHandler('createTicket', (data) => {
    assert.deepEqual(data, payload)
    return success(created)
  })

  const result = await store.createTicket(payload)

  assert.deepEqual(result, created)
  assert.deepEqual(store.currentTicket, created)
  assert.deepEqual(store.tickets, [ticket])
  assert.deepEqual(store.pagination, {
    count: 1,
    next: null,
    previous: null
  })
  assert.equal(store.isMutating, false)
})

test('updateTicket synchronizes the current ticket', async () => {
  const store = createStore()
  store.currentTicket = ticket
  const payload = {
    title: '更新后的标题',
    description: '更新后的描述',
    category: 2
  }
  const updated = {
    ...ticket,
    ...payload,
    category: { id: 2, name: '系统问题' }
  }
  mockApi.setMockHandler('updateTicket', (id, data) => {
    assert.deepEqual([id, data], [12, payload])
    return success(updated)
  })

  const result = await store.updateTicket(12, payload)

  assert.deepEqual(result, updated)
  assert.deepEqual(store.currentTicket, updated)
  assert.equal(store.isMutating, false)
})

test('assignTicket updates matching list and current ticket', async () => {
  const store = createStore()
  store.tickets = [ticket, { ...ticket, id: 13 }]
  store.currentTicket = ticket
  const assigned = {
    ...ticket,
    assignee: {
      id: 8,
      username: 'handler',
      email: 'handler@example.com'
    }
  }
  mockApi.setMockHandler('assignTicket', (id, assigneeId) => {
    assert.deepEqual([id, assigneeId], [12, 8])
    return success(assigned)
  })

  await store.assignTicket(12, 8)

  assert.deepEqual(store.tickets[0], assigned)
  assert.deepEqual(store.currentTicket, assigned)

  mockApi.setMockHandler('assignTicket', (id, assigneeId) => {
    assert.deepEqual([id, assigneeId], [12, null])
    return success({ ...assigned, assignee: null })
  })
  await store.assignTicket(12, null)

  assert.equal(store.tickets[0].assignee, null)
  assert.equal(store.currentTicket.assignee, null)
})

test('processTicket synchronizes status', async () => {
  const store = createStore()
  store.tickets = [ticket]
  store.currentTicket = ticket
  mockApi.setMockHandler('processTicket', (id, status) => {
    assert.deepEqual([id, status], [12, 'processing'])
    return success({ ...ticket, status: 'processing' })
  })

  await store.processTicket(12, 'processing')
  assert.equal(store.tickets[0].status, 'processing')
  assert.equal(store.currentTicket.status, 'processing')
})

test('closeTicket synchronizes status', async () => {
  const store = createStore()
  store.tickets = [{ ...ticket, status: 'resolved' }]
  store.currentTicket = { ...ticket, status: 'resolved' }
  mockApi.setMockHandler('closeTicket', (id) => {
    assert.equal(id, 12)
    return success({ ...ticket, status: 'closed' })
  })

  await store.closeTicket(12)
  assert.equal(store.tickets[0].status, 'closed')
  assert.equal(store.currentTicket.status, 'closed')
})

test('clearCurrentTicket does not clear list or categories', () => {
  const store = createStore()
  store.tickets = [ticket]
  store.categories = [{ id: 1, name: '网络问题' }]
  store.currentTicket = ticket

  store.clearCurrentTicket()

  assert.equal(store.currentTicket, null)
  assert.deepEqual(store.tickets, [ticket])
  assert.deepEqual(store.categories, [{ id: 1, name: '网络问题' }])
})

test('loading state is true while a list request is pending', async () => {
  const store = createStore()
  const pending = deferred()
  mockApi.setMockHandler('getTickets', () => pending.promise)

  const request = store.fetchTickets()
  assert.equal(store.isLoading, true)

  pending.resolve({
    data: {
      count: 1,
      next: null,
      previous: null,
      results: [ticket]
    }
  })
  await request

  assert.equal(store.isLoading, false)
})

test('older list response cannot overwrite a newer request', async () => {
  const store = createStore()
  const first = deferred()
  const second = deferred()
  let requestCount = 0
  mockApi.setMockHandler('getTickets', () => {
    requestCount += 1
    return requestCount === 1 ? first.promise : second.promise
  })

  const firstRequest = store.fetchTickets({ page: 1 })
  const secondRequest = store.fetchTickets({ page: 2 })

  second.resolve({
    data: {
      count: 2,
      next: null,
      previous: null,
      results: [{ ...ticket, id: 2, title: '新结果' }]
    }
  })
  await secondRequest
  first.resolve({
    data: {
      count: 1,
      next: null,
      previous: null,
      results: [{ ...ticket, id: 1, title: '旧结果' }]
    }
  })
  await firstRequest

  assert.deepEqual(store.tickets, [{ ...ticket, id: 2, title: '新结果' }])
  assert.equal(store.pagination.count, 2)
  assert.equal(store.isLoading, false)
})

test('older filtered response cannot overwrite newer filtered results', async () => {
  const store = createStore()
  const first = deferred()
  const second = deferred()
  let requestCount = 0
  mockApi.setMockHandler('getTickets', () => {
    requestCount += 1
    return requestCount === 1 ? first.promise : second.promise
  })

  const firstRequest = store.fetchTickets({
    status: 'pending',
    priority: 'low'
  })
  const secondRequest = store.fetchTickets({
    status: 'closed',
    priority: 'urgent'
  })

  second.resolve({
    data: {
      count: 1,
      next: null,
      previous: null,
      results: [{
        ...ticket,
        id: 20,
        title: '最新筛选结果',
        status: 'closed',
        priority: 'urgent'
      }]
    }
  })
  await secondRequest
  first.resolve({
    data: {
      count: 1,
      next: null,
      previous: null,
      results: [{
        ...ticket,
        id: 19,
        title: '旧筛选结果',
        status: 'pending',
        priority: 'low'
      }]
    }
  })
  await firstRequest

  assert.equal(store.tickets[0].id, 20)
  assert.equal(store.tickets[0].title, '最新筛选结果')
  assert.equal(store.isLoading, false)
})

test('older detail response cannot overwrite a newer request', async () => {
  const store = createStore()
  const first = deferred()
  const second = deferred()
  let requestCount = 0
  mockApi.setMockHandler('getTicket', () => {
    requestCount += 1
    return requestCount === 1 ? first.promise : second.promise
  })

  const firstRequest = store.fetchTicket(1)
  const secondRequest = store.fetchTicket(2)

  second.resolve({ data: { ...ticket, id: 2, title: '新详情' } })
  await secondRequest
  first.resolve({ data: { ...ticket, id: 1, title: '旧详情' } })
  await firstRequest

  assert.equal(store.currentTicket.id, 2)
  assert.equal(store.currentTicket.title, '新详情')
  assert.equal(store.isDetailLoading, false)
})
