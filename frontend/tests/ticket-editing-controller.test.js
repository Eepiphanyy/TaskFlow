import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ref } from 'vue'

import {
  canEditTicket,
  createTicketEditingController,
  getEditingErrorMessage
} from '../src/composables/ticketEditingController.js'

const adminUser = {
  id: 1,
  roles: [{ code: 'admin' }],
  department: { id: 3, name: '研发部' },
  permissions: ['tickets.change_ticket']
}
const managerUser = {
  id: 2,
  roles: [{ code: 'department_manager' }],
  department: { id: 3, name: '研发部' },
  permissions: ['tickets.change_ticket']
}
const employeeUser = {
  id: 8,
  roles: [{ code: 'employee' }],
  department: { id: 3, name: '研发部' },
  permissions: ['tickets.change_ticket']
}
const handlerUser = {
  id: 9,
  roles: [{ code: 'ticket_handler' }],
  department: { id: 3, name: '研发部' },
  permissions: ['tickets.change_ticket']
}
const categories = [
  { id: 1, name: '系统问题', description: '系统异常' },
  { id: 2, name: '网络问题', description: '网络异常' }
]

function makeTicket({
  status = 'pending',
  creatorId = 8,
  departmentId = 3
} = {}) {
  return {
    id: 12,
    title: '原工单标题',
    description: '原工单描述',
    category: { id: 1, name: '系统问题' },
    creator: { id: creatorId, username: 'creator' },
    department: { id: departmentId, name: '研发部' },
    assignee: null,
    status,
    priority: 'medium'
  }
}

function validFormRef() {
  return {
    value: {
      validate: async () => true
    }
  }
}

function createController({
  user = adminUser,
  ticket = makeTicket(),
  updateTicket = null,
  fetchTicket = null,
  fetchCategories = null
} = {}) {
  const currentTicket = ref(ticket)
  const calls = {
    updateTicket: [],
    fetchTicket: [],
    fetchCategories: 0
  }
  const notifications = []
  const ticketsStore = {
    categories,
    isCategoriesLoading: false,
    async fetchCategories() {
      calls.fetchCategories += 1
      if (fetchCategories) {
        return fetchCategories(calls.fetchCategories)
      }
      return ticketsStore.categories
    },
    async updateTicket(id, data) {
      calls.updateTicket.push([id, data])
      if (updateTicket) {
        return updateTicket(id, data)
      }
      const updated = {
        ...currentTicket.value,
        title: data.title,
        description: data.description,
        category: data.category == null
          ? null
          : categories.find(
            (category) => category.id === data.category
          )
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
  const controller = createTicketEditingController({
    ticketsStore,
    authStore: { user },
    ticketId: ref(String(ticket?.id || 12)),
    currentTicket,
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

test('admin can edit pending and processing tickets', () => {
  assert.equal(
    canEditTicket(adminUser, makeTicket({ status: 'pending' })),
    true
  )
  assert.equal(
    canEditTicket(adminUser, makeTicket({ status: 'processing' })),
    true
  )
})

test('manager can edit only own-department editable tickets', () => {
  assert.equal(
    canEditTicket(
      managerUser,
      makeTicket({ status: 'processing', departmentId: 3 })
    ),
    true
  )
  assert.equal(
    canEditTicket(managerUser, makeTicket({ departmentId: 4 })),
    false
  )
})

test('employee can edit only their own pending ticket', () => {
  assert.equal(
    canEditTicket(employeeUser, makeTicket({ status: 'pending' })),
    true
  )
  assert.equal(
    canEditTicket(
      employeeUser,
      makeTicket({ status: 'pending', creatorId: 10 })
    ),
    false
  )
  assert.equal(
    canEditTicket(employeeUser, makeTicket({ status: 'processing' })),
    false
  )
})

test('ticket handler cannot edit even with change permission', () => {
  assert.equal(
    canEditTicket(handlerUser, makeTicket()),
    false
  )
})

test('resolved and closed tickets cannot be edited', () => {
  assert.equal(
    canEditTicket(adminUser, makeTicket({ status: 'resolved' })),
    false
  )
  assert.equal(
    canEditTicket(adminUser, makeTicket({ status: 'closed' })),
    false
  )
})

test('change permission is required for every role', () => {
  assert.equal(
    canEditTicket(
      { ...adminUser, permissions: [] },
      makeTicket()
    ),
    false
  )
})

test('opening the editor prefills current ticket values', async () => {
  const { controller, calls } = createController()

  assert.equal(await controller.openEditDialog(), true)

  assert.deepEqual(controller.form, {
    title: '原工单标题',
    description: '原工单描述',
    category: 1
  })
  assert.equal(controller.isEditDialogOpen.value, true)
  assert.equal(calls.fetchCategories, 1)
})

test('category loading failure can be retried', async () => {
  let attempts = 0
  const { controller } = createController({
    async fetchCategories() {
      attempts += 1
      if (attempts === 1) {
        const error = new Error('categories failed')
        error.userMessage = '分类加载失败'
        throw error
      }
      return categories
    }
  })

  assert.equal(await controller.openEditDialog(), true)
  assert.equal(controller.categoryLoadError.value, '分类加载失败')
  assert.equal(await controller.loadCategories(), true)
  assert.equal(controller.categoryLoadError.value, '')
})

test('submit sends only editable fields and refreshes detail', async () => {
  const { controller, calls, notifications } = createController()
  await controller.openEditDialog()
  controller.form.title = '  新标题  '
  controller.form.description = '  新描述  '
  controller.form.category = 2

  const result = await controller.submit(validFormRef())

  assert.equal(result, true)
  assert.deepEqual(calls.updateTicket, [[
    '12',
    {
      title: '新标题',
      description: '新描述',
      category: 2
    }
  ]])
  assert.deepEqual(calls.fetchTicket, ['12'])
  assert.deepEqual(notifications, [['success', '工单编辑成功']])
  assert.equal(controller.isEditDialogOpen.value, false)
  assert.equal(controller.isSaving.value, false)
})

test('submit supports clearing the optional category', async () => {
  const { controller, calls } = createController()
  await controller.openEditDialog()
  controller.form.category = null

  await controller.submit(validFormRef())

  assert.equal(calls.updateTicket[0][1].category, null)
})

test('edit failure preserves form input and maps field errors', async () => {
  const error = new Error('validation failed')
  error.userMessage = '工单编辑失败'
  error.response = {
    status: 400,
    data: {
      title: ['标题不可用'],
      category: ['分类无效']
    }
  }
  const { controller } = createController({
    async updateTicket() {
      throw error
    }
  })
  await controller.openEditDialog()
  controller.form.title = '保留标题'
  controller.form.description = '保留描述'
  controller.form.category = 2

  const result = await controller.submit(validFormRef())

  assert.equal(result, false)
  assert.equal(controller.form.title, '保留标题')
  assert.equal(controller.form.description, '保留描述')
  assert.equal(controller.form.category, 2)
  assert.equal(controller.fieldErrors.title, '标题不可用')
  assert.equal(controller.fieldErrors.category, '分类无效')
  assert.equal(controller.saveError.value, '工单编辑失败')
  assert.equal(controller.isSaving.value, false)
})

test('duplicate submit produces one update request', async () => {
  let resolveUpdate
  const { controller, calls } = createController({
    updateTicket: () => new Promise((resolve) => {
      resolveUpdate = resolve
    })
  })
  await controller.openEditDialog()

  const first = controller.submit(validFormRef())
  const second = controller.submit(validFormRef())
  assert.equal(await second, false)

  resolveUpdate(makeTicket())
  await first

  assert.equal(calls.updateTicket.length, 1)
})

test('refresh failure reports warning without false success', async () => {
  const { controller, notifications } = createController({
    async fetchTicket() {
      throw new Error('refresh failed')
    }
  })
  await controller.openEditDialog()

  const result = await controller.submit(validFormRef())

  assert.equal(result, false)
  assert.equal(
    controller.saveError.value,
    '工单已更新，但详情刷新失败，请重新加载'
  )
  assert.deepEqual(notifications, [[
    'warning',
    '工单已更新，但详情刷新失败，请重新加载'
  ]])
})

test('invalid form prevents the update request', async () => {
  const { controller, calls } = createController()
  await controller.openEditDialog()
  const invalidForm = {
    value: {
      validate: async () => {
        throw new Error('invalid')
      }
    }
  }

  assert.equal(await controller.submit(invalidForm), false)
  assert.deepEqual(calls.updateTicket, [])
  assert.equal(controller.isSaving.value, false)
})

test('editing error messages cover 403 404 409 and network', () => {
  assert.equal(
    getEditingErrorMessage({ status: 403 }),
    '无权编辑此工单'
  )
  assert.equal(
    getEditingErrorMessage({ status: 404 }),
    '工单不存在或无权编辑'
  )
  assert.equal(
    getEditingErrorMessage({ status: 409 }),
    '当前工单状态或角色不允许编辑'
  )
  assert.equal(
    getEditingErrorMessage({
      userMessage: '网络连接失败，请检查网络或后端服务'
    }),
    '网络连接失败，请检查网络或后端服务'
  )
})
