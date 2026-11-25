import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ref } from 'vue'

import {
  canProcessTicket,
  createTicketProcessingController,
  getProcessingErrorMessage,
  getTicketProcessingAction
} from '../src/composables/ticketProcessingController.js'

const adminUser = {
  id: 1,
  roles: [{ code: 'admin' }],
  department: { id: 3, name: '研发部' },
  permissions: ['tickets.process_ticket']
}
const managerUser = {
  id: 2,
  roles: [{ code: 'department_manager' }],
  department: { id: 3, name: '研发部' },
  permissions: ['tickets.process_ticket']
}
const handlerUser = {
  id: 8,
  roles: [{ code: 'ticket_handler' }],
  department: { id: 4, name: '运维部' },
  permissions: ['tickets.process_ticket']
}
const employeeUser = {
  id: 9,
  roles: [{ code: 'employee' }],
  department: { id: 3, name: '研发部' },
  permissions: []
}

function makeTicket({
  status = 'pending',
  assignee = null,
  departmentId = 3
} = {}) {
  return {
    id: 12,
    title: '网络中断',
    status,
    priority: 'high',
    assignee,
    department: { id: departmentId, name: '研发部' }
  }
}

function createController({
  user = adminUser,
  ticket = makeTicket(),
  processTicket = null,
  fetchTicket = null
} = {}) {
  const currentTicket = ref(ticket)
  const calls = {
    processTicket: [],
    fetchTicket: []
  }
  const notifications = []
  const ticketsStore = {
    async processTicket(id, status) {
      calls.processTicket.push([id, status])
      if (processTicket) {
        return processTicket(id, status)
      }
      const updated = {
        ...currentTicket.value,
        status
      }
      currentTicket.value = updated
      return updated
    },
    async fetchTicket(id) {
      calls.fetchTicket.push(id)
      if (fetchTicket) {
        return fetchTicket(id)
      }
      return currentTicket.value
    }
  }
  const controller = createTicketProcessingController({
    ticketsStore,
    authStore: { user },
    ticketId: ref(String(ticket?.id || 12)),
    currentTicket,
    notifySuccess: (message) => {
      notifications.push(['success', message])
    },
    notifyError: (message) => {
      notifications.push(['error', message])
    }
  })

  return {
    controller,
    currentTicket,
    calls,
    notifications
  }
}

test('pending tickets map to the processing action', () => {
  assert.deepEqual(
    getTicketProcessingAction(makeTicket({ status: 'pending' })),
    {
      targetStatus: 'processing',
      label: '开始处理',
      successMessage: '工单已开始处理'
    }
  )
})

test('processing tickets map to the resolved action', () => {
  assert.deepEqual(
    getTicketProcessingAction(makeTicket({ status: 'processing' })),
    {
      targetStatus: 'resolved',
      label: '标记解决',
      successMessage: '工单已标记解决'
    }
  )
})

test('resolved and closed tickets have no processing action', () => {
  assert.equal(
    getTicketProcessingAction(makeTicket({ status: 'resolved' })),
    null
  )
  assert.equal(
    getTicketProcessingAction(makeTicket({ status: 'closed' })),
    null
  )
})

test('admin can process both allowed source statuses', () => {
  assert.equal(
    canProcessTicket(adminUser, makeTicket({ status: 'pending' })),
    true
  )
  assert.equal(
    canProcessTicket(adminUser, makeTicket({ status: 'processing' })),
    true
  )
})

test('manager can process only own-department tickets', () => {
  assert.equal(
    canProcessTicket(managerUser, makeTicket({ departmentId: 3 })),
    true
  )
  assert.equal(
    canProcessTicket(managerUser, makeTicket({ departmentId: 4 })),
    false
  )
  assert.equal(
    canProcessTicket(
      { ...managerUser, department: null },
      makeTicket()
    ),
    false
  )
})

test('ticket handler can process only the assigned ticket', () => {
  assert.equal(
    canProcessTicket(
      handlerUser,
      makeTicket({ assignee: { id: 8, username: 'handler' } })
    ),
    true
  )
  assert.equal(
    canProcessTicket(
      handlerUser,
      makeTicket({ assignee: { id: 10, username: 'other' } })
    ),
    false
  )
  assert.equal(
    canProcessTicket(handlerUser, makeTicket({ assignee: null })),
    false
  )
})

test('multiple roles receive the union of eligible branches', () => {
  const multiRoleUser = {
    ...employeeUser,
    permissions: ['tickets.process_ticket'],
    roles: [
      { code: 'employee' },
      { code: 'ticket_handler' }
    ]
  }

  assert.equal(
    canProcessTicket(
      multiRoleUser,
      makeTicket({ assignee: { id: multiRoleUser.id } })
    ),
    true
  )
})

test('employees cannot process tickets', () => {
  assert.equal(
    canProcessTicket(employeeUser, makeTicket({ status: 'pending' })),
    false
  )
})

test('starting processing sends processing and refreshes detail', async () => {
  const { controller, notifications, calls, currentTicket } = (
    createController()
  )

  const result = await controller.processCurrentTicket()

  assert.equal(result, true)
  assert.deepEqual(calls.processTicket, [['12', 'processing']])
  assert.deepEqual(calls.fetchTicket, ['12'])
  assert.equal(currentTicket.value.status, 'processing')
  assert.deepEqual(notifications, [['success', '工单已开始处理']])
  assert.equal(controller.isProcessing.value, false)
})

test('resolving sends resolved and refreshes detail', async () => {
  const ticket = makeTicket({
    status: 'processing',
    assignee: { id: 8, username: 'handler' }
  })
  const { controller, notifications, calls, currentTicket } = (
    createController({ user: handlerUser, ticket })
  )

  const result = await controller.processCurrentTicket()

  assert.equal(result, true)
  assert.deepEqual(calls.processTicket, [['12', 'resolved']])
  assert.deepEqual(calls.fetchTicket, ['12'])
  assert.equal(currentTicket.value.status, 'resolved')
  assert.deepEqual(notifications, [['success', '工单已标记解决']])
})

test('refresh failure does not report processing success', async () => {
  const { controller, notifications } = createController({
    async fetchTicket() {
      throw new Error('refresh failed')
    }
  })

  const result = await controller.processCurrentTicket()

  assert.equal(result, false)
  assert.equal(
    controller.processError.value,
    '工单状态已更新，但详情刷新失败'
  )
  assert.deepEqual(notifications, [[
    'error',
    '工单状态已更新，但详情刷新失败'
  ]])
})

test('403 maps to a permission error', () => {
  assert.equal(
    getProcessingErrorMessage({ status: 403 }),
    '无权处理此工单'
  )
})

test('404 and 409 map to stable business errors', () => {
  assert.equal(
    getProcessingErrorMessage({ response: { status: 404 } }),
    '工单不存在或无权处理'
  )
  assert.equal(
    getProcessingErrorMessage({ status: 409 }),
    '当前工单状态不允许该处理操作'
  )
})

test('network failures use the interceptor message', () => {
  assert.equal(
    getProcessingErrorMessage({
      userMessage: '网络连接失败，请检查网络或后端服务'
    }),
    '网络连接失败，请检查网络或后端服务'
  )
})

test('request failure preserves the detail and restores loading', async () => {
  const originalTicket = makeTicket()
  const error = new Error('conflict')
  error.status = 409
  const { controller, currentTicket, notifications } = createController({
    ticket: originalTicket,
    async processTicket() {
      throw error
    }
  })

  const result = await controller.processCurrentTicket()

  assert.equal(result, false)
  assert.deepEqual(currentTicket.value, originalTicket)
  assert.equal(
    controller.processError.value,
    '当前工单状态不允许该处理操作'
  )
  assert.equal(controller.isProcessing.value, false)
  assert.deepEqual(notifications, [[
    'error',
    '当前工单状态不允许该处理操作'
  ]])
})

test('concurrent clicks produce only one processing request', async () => {
  let resolveProcess
  const { controller, calls } = createController({
    processTicket: () => new Promise((resolve) => {
      resolveProcess = resolve
    })
  })

  const first = controller.processCurrentTicket()
  const second = controller.processCurrentTicket()
  assert.equal(await second, false)

  resolveProcess(makeTicket({ status: 'processing' }))
  await first

  assert.equal(calls.processTicket.length, 1)
})

test('successful start exposes only the next allowed action', async () => {
  const { controller, calls } = createController()

  assert.equal(await controller.processCurrentTicket(), true)

  assert.equal(controller.processActionLabel.value, '标记解决')
  assert.equal(calls.processTicket.length, 1)
})

test('unsupported status does not call the process API', async () => {
  const { controller, calls } = createController({
    ticket: makeTicket({ status: 'resolved' })
  })

  const result = await controller.processCurrentTicket()

  assert.equal(result, false)
  assert.deepEqual(calls.processTicket, [])
  assert.equal(controller.processError.value, '无权处理此工单')
})

test('custom role with process permission can see the action', () => {
  const customUser = {
    id: 20,
    roles: [{ code: 'custom_processor' }],
    department: { id: 9, name: '外部协作' },
    permissions: ['tickets.process_ticket']
  }

  assert.equal(
    canProcessTicket(customUser, makeTicket({ status: 'pending' })),
    true
  )
})

test('process permission is required even for a default role', () => {
  const adminWithoutPermission = {
    ...adminUser,
    permissions: []
  }

  assert.equal(
    canProcessTicket(adminWithoutPermission, makeTicket()),
    false
  )
})
