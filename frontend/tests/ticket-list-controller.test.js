import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'

import {
  createTicketListController,
  formatTicketDateTime,
  getPriorityPresentation,
  getStatusPresentation
} from '../src/composables/ticketListController.js'

let calls
let categoryCalls
let mountedCallback
let routerCalls
let ticketsStore

function createController() {
  return createTicketListController({
    ticketsStore,
    router: {
      push: async (location) => {
        routerCalls.push(location)
      }
    },
    registerOnMounted: (callback) => {
      mountedCallback = callback
    }
  })
}

beforeEach(() => {
  calls = []
  categoryCalls = 0
  routerCalls = []
  mountedCallback = null
  ticketsStore = {
    tickets: [],
    pagination: {
      count: 0,
      next: null,
      previous: null
    },
    isLoading: false,
    error: '',
    categories: [],
    isCategoriesLoading: false,
    fetchTickets: async (params) => {
      calls.push(params)
      return []
    },
    fetchCategories: async () => {
      categoryCalls += 1
      ticketsStore.categories = [
        { id: 1, name: '系统问题' },
        { id: 2, name: '网络问题' }
      ]
      return ticketsStore.categories
    }
  }
})

test('ticket list controller loads tickets when page mounts', async () => {
  createController()

  assert.equal(typeof mountedCallback, 'function')
  await mountedCallback()

  assert.equal(categoryCalls, 1)
  assert.deepEqual(calls, [{
    page: 1,
    page_size: 10,
    ordering: '-created_at'
  }])
})

test('search resets to first page and sends title keyword', async () => {
  const controller = createController()
  controller.currentPage.value = 3
  controller.searchQuery.value = '  网络  '

  await controller.handleSearch()

  assert.deepEqual(calls.at(-1), {
    page: 1,
    page_size: 10,
    ordering: '-created_at',
    search: '网络'
  })
})

test('clear search resets keyword and current page', async () => {
  const controller = createController()
  controller.currentPage.value = 2
  controller.searchQuery.value = '网络'

  await controller.handleClearSearch()

  assert.equal(controller.searchQuery.value, '')
  assert.deepEqual(calls.at(-1), {
    page: 1,
    page_size: 10,
    ordering: '-created_at'
  })
})

test('page and page-size changes preserve search and ordering', async () => {
  const controller = createController()
  controller.searchQuery.value = '系统'
  controller.ordering.value = '-updated_at'
  controller.filterStatus.value = 'processing'
  controller.filterPriority.value = 'high'
  controller.filterCategory.value = 2
  controller.createdAfter.value = '2026-11-01'
  controller.createdBefore.value = '2026-11-30'

  await controller.handlePageChange(2)
  await controller.handlePageSizeChange(20)

  assert.deepEqual(calls[0], {
    page: 2,
    page_size: 10,
    ordering: '-updated_at',
    search: '系统',
    status: 'processing',
    priority: 'high',
    category: 2,
    created_after: '2026-11-01',
    created_before: '2026-11-30'
  })
  assert.deepEqual(calls[1], {
    page: 1,
    page_size: 20,
    ordering: '-updated_at',
    search: '系统',
    status: 'processing',
    priority: 'high',
    category: 2,
    created_after: '2026-11-01',
    created_before: '2026-11-30'
  })
})

test('ordering change resets page and sends supported ordering', async () => {
  const controller = createController()
  controller.currentPage.value = 4
  controller.ordering.value = 'title'

  await controller.handleOrderingChange()

  assert.deepEqual(calls.at(-1), {
    page: 1,
    page_size: 10,
    ordering: 'title'
  })
})

test('clicking a ticket navigates to its detail route', async () => {
  const controller = createController()

  await controller.openTicket({ id: 42 })

  assert.deepEqual(routerCalls, [{
    name: 'ticket-detail',
    params: { id: 42 }
  }])
})

test('duplicate in-flight query is not requested twice', async () => {
  let resolveRequest
  ticketsStore.isLoading = true
  ticketsStore.fetchTickets = (params) => {
    calls.push(params)
    return new Promise((resolve) => {
      resolveRequest = () => {
        ticketsStore.isLoading = false
        resolve([])
      }
    })
  }
  const controller = createController()

  const first = controller.loadTickets()
  const second = controller.loadTickets()
  assert.equal(await second, false)
  assert.equal(calls.length, 1)

  resolveRequest()
  await first
})

test('status priority and date presentation use backend values', () => {
  assert.deepEqual(getStatusPresentation('pending'), {
    label: '待处理',
    type: 'info'
  })
  assert.deepEqual(getPriorityPresentation('urgent'), {
    label: '紧急',
    type: 'danger'
  })
  assert.equal(formatTicketDateTime(''), '-')
  assert.equal(formatTicketDateTime('not-a-date'), 'not-a-date')
})

test('status filter resets page and sends status', async () => {
  const controller = createController()
  controller.currentPage.value = 3
  controller.filterStatus.value = 'pending'

  await controller.handleApplyFilters()

  assert.deepEqual(calls.at(-1), {
    page: 1,
    page_size: 10,
    ordering: '-created_at',
    status: 'pending'
  })
})

test('priority and category filters send backend enum and category id', async () => {
  const controller = createController()
  controller.filterPriority.value = 'urgent'
  controller.filterCategory.value = 2

  await controller.handleApplyFilters()

  assert.deepEqual(calls.at(-1), {
    page: 1,
    page_size: 10,
    ordering: '-created_at',
    priority: 'urgent',
    category: 2
  })
})

test('created date filters use YYYY-MM-DD parameters', async () => {
  const controller = createController()
  controller.createdAfter.value = '2026-11-01'
  controller.createdBefore.value = '2026-11-30'

  await controller.handleApplyFilters()

  assert.deepEqual(calls.at(-1), {
    page: 1,
    page_size: 10,
    ordering: '-created_at',
    created_after: '2026-11-01',
    created_before: '2026-11-30'
  })
})

test('all filters combine with search ordering and pagination', async () => {
  const controller = createController()
  controller.searchQuery.value = '网络'
  controller.ordering.value = 'title'
  controller.pageSize.value = 20
  controller.currentPage.value = 4
  controller.filterStatus.value = 'processing'
  controller.filterPriority.value = 'high'
  controller.filterCategory.value = 1
  controller.createdAfter.value = '2026-11-01'
  controller.createdBefore.value = '2026-11-30'

  await controller.handleApplyFilters()

  assert.deepEqual(calls.at(-1), {
    page: 1,
    page_size: 20,
    ordering: 'title',
    search: '网络',
    status: 'processing',
    priority: 'high',
    category: 1,
    created_after: '2026-11-01',
    created_before: '2026-11-30'
  })
})

test('clear filters restores the original list query', async () => {
  const controller = createController()
  controller.currentPage.value = 3
  controller.filterStatus.value = 'closed'
  controller.filterPriority.value = 'low'
  controller.filterCategory.value = 2
  controller.createdAfter.value = '2026-11-01'
  controller.createdBefore.value = '2026-11-30'

  await controller.handleClearFilters()

  assert.equal(controller.filterStatus.value, '')
  assert.equal(controller.filterPriority.value, '')
  assert.equal(controller.filterCategory.value, null)
  assert.equal(controller.createdAfter.value, '')
  assert.equal(controller.createdBefore.value, '')
  assert.deepEqual(calls.at(-1), {
    page: 1,
    page_size: 10,
    ordering: '-created_at'
  })
})

test('invalid date range is rejected before requesting tickets', async () => {
  const controller = createController()
  controller.createdAfter.value = '2026-12-01'
  controller.createdBefore.value = '2026-11-01'

  assert.equal(await controller.handleApplyFilters(), false)
  assert.deepEqual(calls, [])
  assert.equal(
    controller.filterError.value,
    '创建结束日期不能早于开始日期'
  )
})

test('category loading failure exposes retry', async () => {
  let attempts = 0
  ticketsStore.fetchCategories = async () => {
    attempts += 1
    if (attempts === 1) {
      const error = new Error('category failed')
      error.userMessage = '分类加载失败'
      throw error
    }
    return ticketsStore.categories
  }
  const controller = createController()

  assert.equal(await controller.loadCategories(), false)
  assert.equal(controller.categoryLoadError.value, '分类加载失败')
  assert.equal(await controller.loadCategories(), true)
  assert.equal(controller.categoryLoadError.value, '')
})
