import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ref } from 'vue'

import {
  canCloseTicket,
  createTicketClosingController,
  getClosingErrorMessage
} from '../src/composables/ticketClosingController.js'

const adminUser = {
  id: 1,
  roles: [{ code: 'admin' }],
  department: { id: 3, name: '研发部' },
  permissions: ['tickets.close_ticket']
}
const managerUser = {
  id: 2,
  roles: [{ code: 'department_manager' }],
  department: { id: 3, name: '研发部' },
  permissions: ['tickets.close_ticket']
}
const handlerUser = {
  id: 8,
  roles: [{ code: 'ticket_handler' }],
  department: { id: 4, name: '运维部' },
  permissions: ['tickets.close_ticket']
}
const employeeUser = {
  id: 9,
  roles: [{ code: 'employee' }],
  department: { id: 3, name: '研发部' },
  permissions: []
}

function makeTicket({
  status = 'resolved',
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
  confirmClose = async () => true,
  closeTicket = null,
  fetchTicket = null
} = {}) {
  const currentTicket = ref(ticket)
  const calls = {
    confirmClose: 0,
    closeTicket: [],
    fetchTicket: []
  }
  const notifications = []
  const ticketsStore = {
    async closeTicket(id) {
      calls.closeTicket.push(id)
      if (closeTicket) {
        return closeTicket(id)
      }
      const updated = {
        ...currentTicket.value,
        status: 'closed'
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
  const controller = createTicketClosingController({
    ticketsStore,
    authStore: { user },
    ticketId: ref(String(ticket?.id || 12)),
    currentTicket,
    confirmClose: () => {
      calls.confirmClose += 1
      return confirmClose()
    },
    notifySuccess: (message) => {
      notifications.push(['success', message])
    },
    notifyWarning: (message) => {
      notifications.push(['warning', message])
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

test('admin can close a resolved ticket', () => {
  assert.equal(
    canCloseTicket(adminUser, makeTicket({ status: 'resolved' })),
    true
  )
})

test('pending and processing tickets cannot be closed', () => {
  assert.equal(
    canCloseTicket(adminUser, makeTicket({ status: 'pending' })),
    false
  )
  assert.equal(
    canCloseTicket(adminUser, makeTicket({ status: 'processing' })),
    false
  )
})

test('closed tickets cannot be closed repeatedly', () => {
  assert.equal(
    canCloseTicket(adminUser, makeTicket({ status: 'closed' })),
    false
  )
})

test('manager can close only own-department tickets', () => {
  assert.equal(
    canCloseTicket(managerUser, makeTicket({ departmentId: 3 })),
    true
  )
  assert.equal(
    canCloseTicket(managerUser, makeTicket({ departmentId: 4 })),
    false
  )
  assert.equal(
    canCloseTicket(
      { ...managerUser, department: null },
      makeTicket()
    ),
    false
  )
})

test('ticket handler can close only the assigned ticket', () => {
  assert.equal(
    canCloseTicket(
      handlerUser,
      makeTicket({ assignee: { id: 8, username: 'handler' } })
    ),
    true
  )
  assert.equal(
    canCloseTicket(
      handlerUser,
      makeTicket({ assignee: { id: 10, username: 'other' } })
    ),
    false
  )
  assert.equal(
    canCloseTicket(handlerUser, makeTicket({ assignee: null })),
    false
  )
})

test('employees cannot close tickets', () => {
  assert.equal(
    canCloseTicket(employeeUser, makeTicket()),
    false
  )
})

test('multiple roles receive the union of eligible close branches', () => {
  const multiRoleUser = {
    ...employeeUser,
    permissions: ['tickets.close_ticket'],
    roles: [
      { code: 'employee' },
      { code: 'ticket_handler' }
    ]
  }

  assert.equal(
    canCloseTicket(
      multiRoleUser,
      makeTicket({ assignee: { id: multiRoleUser.id } })
    ),
    true
  )
})

test('confirmed close calls the store and refreshes the detail', async () => {
  const { controller, calls, notifications, currentTicket } = (
    createController()
  )

  const result = await controller.closeCurrentTicket()

  assert.equal(result, true)
  assert.equal(calls.confirmClose, 1)
  assert.deepEqual(calls.closeTicket, ['12'])
  assert.deepEqual(calls.fetchTicket, ['12'])
  assert.equal(currentTicket.value.status, 'closed')
  assert.deepEqual(notifications, [['success', '工单已关闭']])
  assert.equal(controller.isClosing.value, false)
})

test('cancelled confirmation does not call the close API', async () => {
  const { controller, calls } = createController({
    confirmClose: async () => false
  })

  const result = await controller.closeCurrentTicket()

  assert.equal(result, false)
  assert.equal(calls.confirmClose, 1)
  assert.deepEqual(calls.closeTicket, [])
  assert.deepEqual(calls.fetchTicket, [])
})

test('confirmation rejection is treated as cancellation', async () => {
  const { controller, calls } = createController({
    confirmClose: async () => {
      throw new Error('cancel')
    }
  })

  assert.equal(await controller.closeCurrentTicket(), false)
  assert.deepEqual(calls.closeTicket, [])
  assert.equal(controller.closeError.value, '')
})

test('403 maps to a close permission error', async () => {
  const error = new Error('forbidden')
  error.status = 403
  const { controller, notifications } = createController({
    async closeTicket() {
      throw error
    }
  })

  assert.equal(await controller.closeCurrentTicket(), false)
  assert.equal(controller.closeError.value, '无权关闭此工单')
  assert.deepEqual(notifications, [['error', '无权关闭此工单']])
})

test('404 maps to a resource access error', () => {
  assert.equal(
    getClosingErrorMessage({ response: { status: 404 } }),
    '工单不存在或无权操作'
  )
})

test('409 maps to a state conflict error', () => {
  assert.equal(
    getClosingErrorMessage({ status: 409 }),
    '当前工单状态不允许关闭'
  )
})

test('network failures use the existing interceptor message', () => {
  assert.equal(
    getClosingErrorMessage({
      userMessage: '网络连接失败，请检查网络或后端服务'
    }),
    '网络连接失败，请检查网络或后端服务'
  )
})

test('close failure preserves the existing detail', async () => {
  const originalTicket = makeTicket()
  const error = new Error('conflict')
  error.status = 409
  const { controller, currentTicket } = createController({
    ticket: originalTicket,
    async closeTicket() {
      throw error
    }
  })

  assert.equal(await controller.closeCurrentTicket(), false)
  assert.deepEqual(currentTicket.value, originalTicket)
  assert.equal(controller.isClosing.value, false)
})

test('repeated clicks during confirmation create one request flow', async () => {
  let resolveConfirmation
  const { controller, calls } = createController({
    confirmClose: () => new Promise((resolve) => {
      resolveConfirmation = resolve
    })
  })

  const first = controller.closeCurrentTicket()
  const second = controller.closeCurrentTicket()
  assert.equal(await second, false)

  resolveConfirmation(true)
  await first

  assert.equal(calls.confirmClose, 1)
  assert.equal(calls.closeTicket.length, 1)
})

test('repeated clicks while closing create one request', async () => {
  let resolveClose
  const { controller, calls } = createController({
    closeTicket: () => new Promise((resolve) => {
      resolveClose = resolve
    })
  })

  const first = controller.closeCurrentTicket()
  await Promise.resolve()
  const second = controller.closeCurrentTicket()
  assert.equal(await second, false)

  resolveClose(makeTicket({ status: 'closed' }))
  await first

  assert.equal(calls.closeTicket.length, 1)
})

test('refresh failure reports a warning without false success', async () => {
  const { controller, notifications } = createController({
    async fetchTicket() {
      throw new Error('refresh failed')
    }
  })

  const result = await controller.closeCurrentTicket()

  assert.equal(result, false)
  assert.equal(
    controller.closeError.value,
    '工单已关闭，但详情刷新失败，请重新加载'
  )
  assert.equal(controller.closeErrorType.value, 'warning')
  assert.deepEqual(notifications, [[
    'warning',
    '工单已关闭，但详情刷新失败，请重新加载'
  ]])
})

test('unsupported status does not request confirmation or close', async () => {
  const { controller, calls } = createController({
    ticket: makeTicket({ status: 'processing' })
  })

  assert.equal(await controller.closeCurrentTicket(), false)
  assert.equal(calls.confirmClose, 0)
  assert.deepEqual(calls.closeTicket, [])
  assert.equal(controller.closeError.value, '无权关闭此工单')
})

test('custom role with close permission can see the action', () => {
  const customUser = {
    id: 21,
    roles: [{ code: 'custom_closer' }],
    department: { id: 9, name: '外部协作' },
    permissions: ['tickets.close_ticket']
  }

  assert.equal(
    canCloseTicket(customUser, makeTicket({ status: 'resolved' })),
    true
  )
})

test('close permission is required even for a default role', () => {
  const adminWithoutPermission = {
    ...adminUser,
    permissions: []
  }

  assert.equal(
    canCloseTicket(adminWithoutPermission, makeTicket()),
    false
  )
})
