import request from '@/utils/request'

const LIST_QUERY_KEYS = [
  'page',
  'page_size',
  'search',
  'ordering',
  'status',
  'priority',
  'category',
  'created_after',
  'created_before'
]
const PROCESS_STATUSES = ['processing', 'resolved']

function ticketPath(ticketId, suffix = '') {
  if (ticketId === undefined || ticketId === null || ticketId === '') {
    throw new TypeError('ticketId is required')
  }

  const encodedId = encodeURIComponent(ticketId)
  return `/tickets/${encodedId}/${suffix}`
}

export function getTickets(params = {}) {
  const query = Object.fromEntries(
    LIST_QUERY_KEYS
      .filter((key) => params[key] !== undefined)
      .map((key) => [key, params[key]])
  )

  return request.get('/tickets/', { params: query })
}

export function getTicket(ticketId) {
  return request.get(ticketPath(ticketId))
}

export function updateTicket(ticketId, data) {
  const payload = {}
  for (const field of ['title', 'description', 'category']) {
    if (data[field] !== undefined) {
      payload[field] = data[field]
    }
  }

  return request.patch(ticketPath(ticketId), payload)
}

export function createTicket(data) {
  const payload = {
    title: data.title,
    description: data.description
  }

  if (data.category !== undefined) {
    payload.category = data.category
  }

  return request.post('/tickets/', payload)
}

export function getTicketCategories() {
  return request.get('/ticket-categories/')
}

export function getTicketAssignees() {
  return request.get('/tickets/assignees/')
}

export function assignTicket(ticketId, assigneeId) {
  return request.patch(
    ticketPath(ticketId, 'assign/'),
    { assignee_id: assigneeId }
  )
}

export function processTicket(ticketId, status) {
  if (!PROCESS_STATUSES.includes(status)) {
    throw new TypeError('status must be processing or resolved')
  }

  return request.patch(
    ticketPath(ticketId, 'process/'),
    { status }
  )
}

export function closeTicket(ticketId) {
  return request.post(ticketPath(ticketId, 'close/'))
}
