import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'

import {
  createTicketCreateController,
  createTicketRules,
  isValidTicketId
} from '../src/composables/ticketCreateController.js'

let categoriesCalls
let createCalls
let mountedCallback
let notifications
let routerCalls
let ticketsStore

function validFormRef() {
  return {
    value: {
      validate: async () => true
    }
  }
}

function createController() {
  return createTicketCreateController({
    ticketsStore,
    router: {
      push: async (location) => {
        routerCalls.push(location)
      }
    },
    notifySuccess: (message) => {
      notifications.push(['success', message])
    },
    notifyError: (message) => {
      notifications.push(['error', message])
    },
    registerOnMounted: (callback) => {
      mountedCallback = callback
    }
  })
}

function runValidator(validator, value) {
  return new Promise((resolve) => {
    validator({}, value, (error) => resolve(error))
  })
}

beforeEach(() => {
  categoriesCalls = 0
  createCalls = []
  mountedCallback = null
  notifications = []
  routerCalls = []
  ticketsStore = {
    categories: [],
    isCategoriesLoading: false,
    createTicket: async (data) => {
      createCalls.push(data)
      return {
        id: 21,
        ...data
      }
    },
    fetchCategories: async () => {
      categoriesCalls += 1
      ticketsStore.categories = [
        { id: 1, name: '系统问题', description: '系统异常' }
      ]
      return ticketsStore.categories
    }
  }
})

test('page mount loads categories through the store', async () => {
  createController()

  assert.equal(typeof mountedCallback, 'function')
  await mountedCallback()

  assert.equal(categoriesCalls, 1)
})

test('category options come from store data', async () => {
  const controller = createController()

  await controller.loadCategories()

  assert.deepEqual(controller.categories.value, [
    { id: 1, name: '系统问题', description: '系统异常' }
  ])
})

test('category failure exposes retry and can recover', async () => {
  let shouldFail = true
  const failure = new Error('category failed')
  failure.userMessage = '分类加载失败'
  ticketsStore.fetchCategories = async () => {
    categoriesCalls += 1
    if (shouldFail) {
      throw failure
    }
    ticketsStore.categories = [{ id: 2, name: '网络问题' }]
    return ticketsStore.categories
  }
  const controller = createController()

  assert.equal(await controller.loadCategories(), false)
  assert.equal(controller.categoryLoadError.value, '分类加载失败')

  shouldFail = false
  assert.equal(await controller.loadCategories(), true)
  assert.equal(controller.categoryLoadError.value, '')
  assert.deepEqual(controller.categories.value, [
    { id: 2, name: '网络问题' }
  ])
})

test('title is required and limited to backend max length', async () => {
  const validator = createTicketRules.title[0].validator

  assert.equal(
    (await runValidator(validator, '   ')).message,
    '请输入工单标题'
  )
  assert.equal(await runValidator(validator, '有效标题'), undefined)
  assert.equal(createTicketRules.title[1].max, 200)
})

test('description is required and category remains optional', async () => {
  const validator = createTicketRules.description[0].validator

  assert.equal(
    (await runValidator(validator, '')).message,
    '请输入问题描述'
  )
  assert.equal(await runValidator(validator, '有效描述'), undefined)
  assert.equal('category' in createTicketRules, false)
})

test('submit sends only title description and category', async () => {
  const controller = createController()
  controller.form.title = '  网络中断  '
  controller.form.description = '  无法访问网络  '
  controller.form.category = 1

  const result = await controller.submit(validFormRef())

  assert.equal(result, true)
  assert.deepEqual(createCalls, [{
    title: '网络中断',
    description: '无法访问网络',
    category: 1
  }])
})

test('submit sends null when category is not selected', async () => {
  const controller = createController()
  controller.form.title = '无分类工单'
  controller.form.description = '问题描述'

  await controller.submit(validFormRef())

  assert.deepEqual(createCalls[0], {
    title: '无分类工单',
    description: '问题描述',
    category: null
  })
})

test('creation success navigates to the returned ticket id', async () => {
  const controller = createController()
  controller.form.title = '新工单'
  controller.form.description = '新工单描述'

  const result = await controller.submit(validFormRef())

  assert.equal(result, true)
  assert.deepEqual(routerCalls, [{
    name: 'ticket-detail',
    params: { id: 21 }
  }])
  assert.deepEqual(notifications, [['success', '工单创建成功']])
})

test('creation failure preserves form input and maps field errors', async () => {
  const error = new Error('validation failed')
  error.userMessage = '工单信息校验失败'
  error.response = {
    data: {
      title: ['该标题不可用'],
      description: ['描述格式错误']
    }
  }
  ticketsStore.createTicket = async () => {
    throw error
  }
  const controller = createController()
  controller.form.title = '保留标题'
  controller.form.description = '保留描述'
  controller.form.category = 3

  const result = await controller.submit(validFormRef())

  assert.equal(result, false)
  assert.equal(controller.form.title, '保留标题')
  assert.equal(controller.form.description, '保留描述')
  assert.equal(controller.form.category, 3)
  assert.equal(controller.fieldErrors.title, '该标题不可用')
  assert.equal(controller.fieldErrors.description, '描述格式错误')
  assert.equal(routerCalls.length, 0)
})

test('duplicate submit request is prevented before validation completes', async () => {
  let resolveValidation
  const formRef = {
    value: {
      validate: () => new Promise((resolve) => {
        resolveValidation = resolve
      })
    }
  }
  const controller = createController()
  controller.form.title = '防重复'
  controller.form.description = '描述'

  const first = controller.submit(formRef)
  const second = controller.submit(formRef)
  assert.equal(await second, false)

  resolveValidation(true)
  await first

  assert.equal(createCalls.length, 1)
})

test('invalid validation prevents API submission', async () => {
  const controller = createController()
  const invalidForm = {
    value: {
      validate: async () => {
        throw new Error('invalid')
      }
    }
  }

  assert.equal(await controller.submit(invalidForm), false)
  assert.equal(createCalls.length, 0)
  assert.equal(controller.isSubmitting.value, false)
})

test('missing id after successful creation does not navigate', async () => {
  ticketsStore.createTicket = async () => ({
    id: null,
    title: '异常响应'
  })
  const controller = createController()
  controller.form.title = '异常响应'
  controller.form.description = '描述'

  const result = await controller.submit(validFormRef())

  assert.equal(result, false)
  assert.deepEqual(routerCalls, [])
  assert.equal(
    controller.submitError.value,
    '创建成功，但响应缺少有效工单编号'
  )
})

test('valid ticket ids are positive integers', () => {
  assert.equal(isValidTicketId(1), true)
  assert.equal(isValidTicketId('42'), true)
  assert.equal(isValidTicketId(null), false)
  assert.equal(isValidTicketId(0), false)
  assert.equal(isValidTicketId('invalid'), false)
})
