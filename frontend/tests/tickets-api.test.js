import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { beforeEach, test } from 'node:test'
import { pathToFileURL } from 'node:url'

const ticketsSourceUrl = new URL('../src/api/tickets.js', import.meta.url)
const requestUrl = new URL('../src/utils/request.js', import.meta.url)
const ticketsSource = readFileSync(ticketsSourceUrl, 'utf8')
const transformedSource = ticketsSource.replace(
  "from '@/utils/request'",
  `from '${requestUrl.href}'`
)
const moduleUrl = `data:text/javascript;base64,${
  Buffer.from(transformedSource).toString('base64')
}`

const { default: request } = await import(requestUrl.href)
const {
  assignTicket,
  closeTicket,
  createTicket,
  getTicket,
  getTicketAssignees,
  getTicketCategories,
  getTickets,
  processTicket,
  updateTicket
} = await import(moduleUrl)

let requests

beforeEach(() => {
  requests = []
  request.defaults.adapter = async (config) => {
    requests.push(config)
    return {
      data: {},
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
      request: {}
    }
  }
})

test('tickets API uses the shared request module', () => {
  assert.match(
    ticketsSource,
    /import request from '@\/utils\/request'/
  )
  assert.doesNotMatch(ticketsSource, /from 'axios'/)
  assert.equal(request.defaults.baseURL, '/api')
})

test('getTickets sends supported query filter search and ordering params', async () => {
  await getTickets({
    page: 2,
    page_size: 20,
    search: '网络',
    ordering: '-created_at',
    status: 'processing',
    priority: 'high',
    category: 3,
    created_after: '2026-11-01',
    created_before: '2026-11-30',
    user_id: 999,
    department_id: 3
  })

  assert.equal(requests[0].method, 'get')
  assert.equal(requests[0].url, '/tickets/')
  assert.deepEqual(requests[0].params, {
    page: 2,
    page_size: 20,
    search: '网络',
    ordering: '-created_at',
    status: 'processing',
    priority: 'high',
    category: 3,
    created_after: '2026-11-01',
    created_before: '2026-11-30'
  })
})

test('getTicket requests the correct detail URL', async () => {
  await getTicket(42)

  assert.equal(requests[0].method, 'get')
  assert.equal(requests[0].url, '/tickets/42/')
})

test('updateTicket sends only editable fields to the detail URL', async () => {
  await updateTicket(42, {
    title: '新标题',
    description: '新描述',
    category: 3,
    creator_id: 99,
    department_id: 2,
    assignee_id: 8,
    status: 'closed',
    priority: 'urgent'
  })

  assert.equal(requests[0].method, 'patch')
  assert.equal(requests[0].url, '/tickets/42/')
  assert.deepEqual(JSON.parse(requests[0].data), {
    title: '新标题',
    description: '新描述',
    category: 3
  })
})

test('updateTicket supports category null and omits unspecified fields', async () => {
  await updateTicket(42, {
    title: '保留描述',
    category: null
  })

  assert.deepEqual(JSON.parse(requests[0].data), {
    title: '保留描述',
    category: null
  })
})

test('createTicket only sends create serializer fields', async () => {
  await createTicket({
    title: '网络中断',
    description: '办公网络无法访问',
    category: 3,
    creator_id: 8,
    department_id: 2
  })

  assert.equal(requests[0].method, 'post')
  assert.equal(requests[0].url, '/tickets/')
  assert.deepEqual(JSON.parse(requests[0].data), {
    title: '网络中断',
    description: '办公网络无法访问',
    category: 3
  })
})

test('createTicket omits an unspecified category', async () => {
  await createTicket({
    title: '无分类工单',
    description: '不传分类'
  })

  assert.deepEqual(JSON.parse(requests[0].data), {
    title: '无分类工单',
    description: '不传分类'
  })
})

test('getTicketCategories requests category list', async () => {
  await getTicketCategories()

  assert.equal(requests[0].method, 'get')
  assert.equal(requests[0].url, '/ticket-categories/')
})

test('getTicketAssignees requests candidates without request fields', async () => {
  const candidates = [
    {
      id: 8,
      username: 'handler',
      department: { id: 2, name: '研发部' }
    }
  ]
  request.defaults.adapter = async (config) => {
    requests.push(config)
    return {
      data: candidates,
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
      request: {}
    }
  }

  const response = await getTicketAssignees()

  assert.equal(requests[0].method, 'get')
  assert.equal(requests[0].url, '/tickets/assignees/')
  assert.equal(requests[0].data, undefined)
  assert.equal(requests[0].params, undefined)
  assert.deepEqual(response.data, candidates)
})

test('assignTicket sends assignee_id for assignment and cancellation', async () => {
  await assignTicket(12, 8)
  await assignTicket(12, null)

  assert.equal(requests[0].method, 'patch')
  assert.equal(requests[0].url, '/tickets/12/assign/')
  assert.deepEqual(JSON.parse(requests[0].data), {
    assignee_id: 8
  })
  assert.deepEqual(JSON.parse(requests[1].data), {
    assignee_id: null
  })
})

test('processTicket sends only supported backend statuses', async () => {
  await processTicket(12, 'processing')
  await processTicket(12, 'resolved')

  assert.equal(requests[0].method, 'patch')
  assert.equal(requests[0].url, '/tickets/12/process/')
  assert.deepEqual(JSON.parse(requests[0].data), {
    status: 'processing'
  })
  assert.deepEqual(JSON.parse(requests[1].data), {
    status: 'resolved'
  })
  assert.throws(
    () => processTicket(12, 'closed'),
    /status must be processing or resolved/
  )
})

test('closeTicket posts without a request body', async () => {
  await closeTicket(12)

  assert.equal(requests[0].method, 'post')
  assert.equal(requests[0].url, '/tickets/12/close/')
  assert.equal(requests[0].data, undefined)
})
