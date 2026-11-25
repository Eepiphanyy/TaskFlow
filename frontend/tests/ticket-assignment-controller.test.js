import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ref } from 'vue'

import {
  canManageTicketAssignment,
  createTicketAssignmentController,
  getAssignmentErrorMessage
} from '../src/composables/ticketAssignmentController.js'

const adminUser = {
  roles: [{ code: 'admin' }],
  department: { id: 3, name: '研发部' },
  permissions: ['tickets.assign_ticket']
}
const managerUser = {
  roles: [{ code: 'department_manager' }],
  department: { id: 3, name: '研发部' },
  permissions: ['tickets.assign_ticket']
}
const employeeUser = {
  roles: [{ code: 'employee' }],
  department: { id: 3, name: '研发部' },
  permissions: []
}
const candidates = [
  {
    id: 8,
    username: 'handler_a',
    department: { id: 3, name: '研发部' }
  },
  {
    id: 9,
    username: 'handler_b',
    department: { id: 4, name: '运维部' }
  }
]

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
  assigneeOptions = candidates,
  fetchAssignees = null,
  assignTicket = null,
  fetchTicket = null,
  storeLoading = false
} = {}) {
  const currentTicket = ref(ticket)
  const calls = {
    fetchAssignees: 0,
    assignTicket: [],
    fetchTicket: []
  }
  const notifications = []
  const ticketsStore = {
    assignees: assigneeOptions,
    isAssigneesLoading: storeLoading,
    async fetchAssignees() {
      calls.fetchAssignees += 1
      if (fetchAssignees) {
        return fetchAssignees(calls.fetchAssignees, ticketsStore)
      }
      return ticketsStore.assignees
    },
    async assignTicket(id, assigneeId) {
      calls.assignTicket.push([id, assigneeId])
      if (assignTicket) {
        return assignTicket(id, assigneeId)
      }
      const updated = {
        ...currentTicket.value,
        assignee: assigneeId == null
          ? null
          : candidates.find((candidate) => candidate.id === assigneeId)
      }
      currentTicket.value = updated
      return updated
    },
    async fetchTicket(id) {
      calls.fetchTicket.push(id)
      if (fetchTicket) {
        return fetchTicket(id, ticketsStore)
      }
      return currentTicket.value
    }
  }
  const controller = createTicketAssignmentController({
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
    notifications,
    calls,
    ticketsStore
  }
}

test('admin and same-department managers can manage assignable tickets', () => {
  assert.equal(
    canManageTicketAssignment(adminUser, makeTicket()),
    true
  )
  assert.equal(
    canManageTicketAssignment(managerUser, makeTicket()),
    true
  )
  assert.equal(
    canManageTicketAssignment(
      managerUser,
      makeTicket({ departmentId: 4 })
    ),
    false
  )
  assert.equal(
    canManageTicketAssignment(employeeUser, makeTicket()),
    false
  )
})

test('resolved and closed tickets never expose assignment actions', () => {
  assert.equal(
    canManageTicketAssignment(adminUser, makeTicket({ status: 'resolved' })),
    false
  )
  assert.equal(
    canManageTicketAssignment(adminUser, makeTicket({ status: 'closed' })),
    false
  )
  assert.equal(
    canManageTicketAssignment(adminUser, makeTicket({ status: 'processing' })),
    true
  )
})

test('candidate list loads through the tickets store', async () => {
  const { controller, calls } = createController()

  const result = await controller.loadAssignees()

  assert.equal(result, true)
  assert.equal(calls.fetchAssignees, 1)
  assert.deepEqual(controller.assignees.value, candidates)
  assert.equal(controller.assigneeError.value, '')
})

test('candidate load failure exposes a retryable error', async () => {
  let attempts = 0
  const { controller } = createController({
    async fetchAssignees() {
      attempts += 1
      if (attempts === 1) {
        const error = new Error('network')
        error.userMessage = '无法加载处理人'
        throw error
      }
      return candidates
    }
  })

  assert.equal(await controller.loadAssignees(), false)
  assert.equal(controller.assigneeError.value, '无法加载处理人')

  assert.equal(await controller.loadAssignees(true), true)
  assert.equal(controller.assigneeError.value, '')
  assert.equal(attempts, 2)
})

test('empty candidate response remains an explicit empty state', async () => {
  const { controller } = createController({
    assigneeOptions: [],
    async fetchAssignees() {
      return []
    }
  })

  assert.equal(await controller.openAssignDialog(), true)

  assert.deepEqual(controller.assignees.value, [])
  assert.equal(controller.isAssignDialogOpen.value, true)
  assert.equal(controller.assigneeError.value, '')
})

test('opening the dialog preselects the current assignee', async () => {
  const currentAssignee = candidates[0]
  const { controller } = createController({
    ticket: makeTicket({ assignee: currentAssignee })
  })

  await controller.openAssignDialog()

  assert.equal(controller.selectedAssigneeId.value, currentAssignee.id)
})

test('assigning an unassigned ticket refreshes the detail', async () => {
  const { controller, notifications, calls } = createController()
  await controller.openAssignDialog()
  controller.selectedAssigneeId.value = 9

  const result = await controller.submitAssignment()

  assert.equal(result, true)
  assert.deepEqual(calls.assignTicket, [['12', 9]])
  assert.deepEqual(calls.fetchTicket, [ '12' ])
  assert.deepEqual(notifications, [['success', '处理人分配成功']])
  assert.equal(controller.isAssignDialogOpen.value, false)
  assert.equal(controller.isAssigning.value, false)
})

test('assigning an already-assigned ticket reports reassignment', async () => {
  const { controller, notifications } = createController({
    ticket: makeTicket({ assignee: candidates[0] })
  })
  await controller.openAssignDialog()
  controller.selectedAssigneeId.value = candidates[1].id

  assert.equal(await controller.submitAssignment(), true)

  assert.deepEqual(notifications, [['success', '处理人重新分配成功']])
})

test('cancellation sends null and refreshes the detail', async () => {
  const { controller, notifications, calls } = createController({
    ticket: makeTicket({ assignee: candidates[0] })
  })

  const result = await controller.cancelAssignment()

  assert.equal(result, true)
  assert.deepEqual(calls.assignTicket, [['12', null]])
  assert.deepEqual(calls.fetchTicket, [ '12' ])
  assert.deepEqual(notifications, [['success', '已取消工单分配']])
})

test('refresh failure does not report assignment success', async () => {
  const { controller, notifications } = createController({
    async fetchTicket() {
      throw new Error('refresh failed')
    }
  })
  await controller.openAssignDialog()
  controller.selectedAssigneeId.value = 8

  const result = await controller.submitAssignment()

  assert.equal(result, false)
  assert.equal(
    controller.operationError.value,
    '处理人已更新，但工单详情刷新失败'
  )
  assert.deepEqual(notifications, [[
    'error',
    '处理人已更新，但工单详情刷新失败'
  ]])
})

test('403, 404, and 409 map to clear assignment errors', () => {
  assert.equal(
    getAssignmentErrorMessage({ status: 403 }),
    '无权分配此工单'
  )
  assert.equal(
    getAssignmentErrorMessage({ response: { status: 404 } }),
    '工单不存在或无权操作'
  )
  assert.equal(
    getAssignmentErrorMessage({ status: 409 }),
    '当前工单状态不允许分配'
  )
})

test('assignment failure keeps the existing detail and closes loading', async () => {
  const originalTicket = makeTicket()
  const error = new Error('forbidden')
  error.status = 403
  const { controller, currentTicket, notifications } = createController({
    ticket: originalTicket,
    async assignTicket() {
      throw error
    }
  })
  await controller.openAssignDialog()
  controller.selectedAssigneeId.value = 8

  const result = await controller.submitAssignment()

  assert.equal(result, false)
  assert.deepEqual(currentTicket.value, originalTicket)
  assert.equal(controller.operationError.value, '无权分配此工单')
  assert.equal(controller.isAssigning.value, false)
  assert.deepEqual(notifications, [['error', '无权分配此工单']])
})

test('duplicate assignment submissions create only one request', async () => {
  let resolveAssignment
  const { controller, calls } = createController({
    assignTicket: () => new Promise((resolve) => {
      resolveAssignment = resolve
    })
  })
  await controller.openAssignDialog()
  controller.selectedAssigneeId.value = 8

  const first = controller.submitAssignment()
  const second = controller.submitAssignment()
  assert.equal(await second, false)

  resolveAssignment(makeTicket({ assignee: candidates[0] }))
  await first

  assert.equal(calls.assignTicket.length, 1)
})

test('candidate loading is not requested twice while already in flight', async () => {
  const { controller, calls } = createController({
    storeLoading: true
  })

  assert.equal(await controller.loadAssignees(true), false)
  assert.equal(calls.fetchAssignees, 0)
})

test('employees cannot open assignment or request candidates', async () => {
  const { controller, calls } = createController({ user: employeeUser })

  assert.equal(await controller.openAssignDialog(), false)
  assert.equal(calls.fetchAssignees, 0)
  assert.equal(controller.isAssignDialogOpen.value, false)
})

test('manager outside the ticket department cannot load candidates', async () => {
  const { controller, calls } = createController({
    user: managerUser,
    ticket: makeTicket({ departmentId: 4 })
  })

  assert.equal(controller.canManageAssignment.value, false)
  assert.equal(await controller.loadAssignees(true), false)
  assert.equal(calls.fetchAssignees, 0)
})

test('resolved tickets reject assignment before calling the store', async () => {
  const { controller, calls } = createController({
    ticket: makeTicket({ status: 'resolved' })
  })
  controller.selectedAssigneeId.value = 8

  assert.equal(await controller.submitAssignment(), false)
  assert.deepEqual(calls.assignTicket, [])
  assert.equal(controller.operationError.value, '无权分配此工单')
})

test('network failures use a user-facing fallback message', () => {
  assert.equal(
    getAssignmentErrorMessage({
      userMessage: '网络连接失败，请检查网络或后端服务'
    }),
    '网络连接失败，请检查网络或后端服务'
  )
  assert.equal(
    getAssignmentErrorMessage(new Error('socket closed')),
    'socket closed'
  )
})

test('custom role with assignment permission can see the action', () => {
  const customUser = {
    roles: [{ code: 'custom_assigner' }],
    department: { id: 4, name: '运维部' },
    permissions: ['tickets.assign_ticket']
  }

  assert.equal(
    canManageTicketAssignment(customUser, makeTicket()),
    true
  )
})

test('assignment permission is required even for a default role', () => {
  const adminWithoutPermission = {
    ...adminUser,
    permissions: []
  }

  assert.equal(
    canManageTicketAssignment(adminWithoutPermission, makeTicket()),
    false
  )
})
