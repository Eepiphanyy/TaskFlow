import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { renderToString } from '@vue/server-renderer'
import ElementPlus, {
  ID_INJECTION_KEY,
  ZINDEX_INJECTION_KEY
} from 'element-plus'
import { createPinia } from 'pinia'
import {
  createSSRApp,
  h,
  inject,
  provide
} from 'vue'
import {
  createMemoryHistory,
  createRouter
} from 'vue-router'
import { createServer } from 'vite'

let viteServer
let useTicketsStore
let useAuthStore

before(async () => {
  viteServer = await createServer({
    appType: 'custom',
    logLevel: 'silent',
    server: {
      middlewareMode: true
    }
  })
  const ticketsStoreModule = await viteServer.ssrLoadModule(
    '/src/stores/tickets.js'
  )
  useTicketsStore = ticketsStoreModule.useTicketsStore
  const authStoreModule = await viteServer.ssrLoadModule(
    '/src/stores/auth.js'
  )
  useAuthStore = authStoreModule.useAuthStore
})

after(async () => {
  await viteServer?.close()
})

async function loadPage(path) {
  const module = await viteServer.ssrLoadModule(path)
  return module.default
}

async function renderPage(
  component,
  initialPath,
  configureStore = null,
  useElementStubs = false,
  configureAuthStore = null
) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/tickets',
        name: 'ticket-list',
        component: { render: () => null }
      },
      {
        path: '/tickets/new',
        name: 'ticket-create',
        component: { render: () => null }
      },
      {
        path: '/tickets/:id',
        name: 'ticket-detail',
        component: { render: () => null }
      }
    ]
  })
  const app = createSSRApp(component)
  const pinia = createPinia()
  app.use(pinia)
  if (configureStore) {
    configureStore(useTicketsStore(pinia))
  }
  if (configureAuthStore) {
    configureAuthStore(useAuthStore(pinia))
  }
  app.provide(ID_INJECTION_KEY, {
    prefix: 100,
    current: 0
  })
  app.provide(ZINDEX_INJECTION_KEY, {
    current: 0
  })
  if (useElementStubs) {
    const stubs = createElementStubs()
    for (const [name, stub] of Object.entries(stubs)) {
      app.component(name, stub)
    }
  } else {
    app.use(ElementPlus)
  }
  app.use(router)

  await router.push(initialPath)
  await router.isReady()
  return renderToString(app)
}

const TABLE_ROWS_KEY = Symbol('table-rows')

function slotContent(slots) {
  return slots.default ? slots.default() : []
}

function createElementStubs() {
  const passthrough = {
    setup(_, { slots }) {
      return () => h('div', {}, slotContent(slots))
    }
  }

  return {
    ElTable: {
      props: ['data'],
      setup(props, { slots }) {
        provide(TABLE_ROWS_KEY, props.data || [])
        return () => h('table', {}, slotContent(slots))
      }
    },
    ElTableColumn: {
      props: ['label'],
      setup(props, { slots }) {
        const rows = inject(TABLE_ROWS_KEY, [])
        return () => h('div', [
          h('strong', {}, props.label),
          ...rows.map((row) => (
            slots.default
              ? slots.default({ row })
              : h('span', {}, '')
          ))
        ])
      }
    },
    ElButton: {
      setup(_, { slots }) {
        return () => h('button', {}, slotContent(slots))
      }
    },
    ElDescriptions: passthrough,
    ElDescriptionsItem: {
      props: ['label'],
      setup(props, { slots }) {
        return () => h('div', [
          h('strong', {}, props.label),
          slotContent(slots)
        ])
      }
    },
    ElTag: {
      setup(_, { slots }) {
        return () => h('span', {}, slotContent(slots))
      }
    },
    ElAlert: passthrough,
    ElCard: passthrough,
    ElDialog: {
      props: ['modelValue'],
      setup(props, { slots }) {
        return () => (
          props.modelValue
            ? h('div', {}, [
                ...slotContent(slots),
                ...(slots.footer ? slots.footer() : [])
              ])
            : null
        )
      }
    },
    ElDatePicker: passthrough,
    ElDivider: passthrough,
    ElEmpty: passthrough,
    ElForm: passthrough,
    ElFormItem: passthrough,
    ElInput: passthrough,
    ElOption: passthrough,
    ElPagination: passthrough,
    ElSelect: passthrough,
    ElSkeleton: passthrough
  }
}

function makeDetailTicket(overrides = {}) {
  return {
    id: 9,
    title: '状态流转工单',
    description: '描述',
    category: null,
    assignee: null,
    status: 'pending',
    priority: 'medium',
    creator: { id: 1, username: 'creator' },
    department: { id: 2, name: '研发部' },
    created_at: '2026-11-24T10:00:00+08:00',
    updated_at: '2026-11-24T10:00:00+08:00',
    ...overrides
  }
}

const ALL_TICKET_PERMISSIONS = [
  'tickets.assign_ticket',
  'tickets.change_ticket',
  'tickets.close_ticket',
  'tickets.process_ticket'
]
const HANDLER_TICKET_PERMISSIONS = [
  'tickets.close_ticket',
  'tickets.process_ticket'
]

test('TicketList page renders heading and navigation entries', async () => {
  const component = await loadPage('/src/views/tickets/TicketList.vue')

  const html = await renderPage(component, '/tickets')

  assert.match(html, /工单列表/)
  assert.match(html, /创建工单/)
  assert.match(html, /暂无工单数据/)
  assert.match(html, /href="\/tickets\/new"/)
  assert.match(html, /状态/)
  assert.match(html, /优先级/)
  assert.match(html, /应用筛选/)
  assert.match(html, /清空筛选/)
  assert.match(html, /创建起始/)
  assert.match(html, /创建结束/)
})

test('TicketList renders category filter options from the store', async () => {
  const component = await loadPage('/src/views/tickets/TicketList.vue')

  const html = await renderPage(component, '/tickets', (store) => {
    store.categories = [
      { id: 1, name: '系统问题' },
      { id: 2, name: '网络问题' }
    ]
  }, true)

  assert.match(html, /系统问题/)
  assert.match(html, /网络问题/)
})

test('TicketList page renders real ticket fields', async () => {
  const component = await loadPage('/src/views/tickets/TicketList.vue')
  const ticket = {
    id: 12,
    title: '网络中断',
    category: { id: 1, name: '网络问题' },
    status: 'processing',
    priority: 'high',
    creator: {
      id: 7,
      username: 'creator',
      email: 'creator@example.com'
    },
    created_at: '2026-11-24T10:00:00+08:00'
  }

  const html = await renderPage(component, '/tickets', (store) => {
    store.tickets = [ticket]
    store.pagination = {
      count: 1,
      next: null,
      previous: null
    }
  }, true)

  assert.match(html, /网络中断/)
  assert.match(html, /网络问题/)
  assert.match(html, /处理中/)
  assert.match(html, /高/)
  assert.match(html, /creator/)
})

test('TicketList page renders loading state', async () => {
  const component = await loadPage('/src/views/tickets/TicketList.vue')

  const html = await renderPage(component, '/tickets', (store) => {
    store.isLoading = true
  })

  assert.match(html, /正在加载工单/)
})

test('TicketList page renders request error and retry', async () => {
  const component = await loadPage('/src/views/tickets/TicketList.vue')

  const html = await renderPage(component, '/tickets', (store) => {
    store.error = '无法加载工单列表'
  })

  assert.match(html, /无法加载工单列表/)
  assert.match(html, /重新加载/)
})

test('TicketCreate page renders form fields and navigation links', async () => {
  const component = await loadPage('/src/views/tickets/TicketCreate.vue')

  const html = await renderPage(component, '/tickets/new')

  assert.match(html, /创建工单/)
  assert.match(html, /工单标题/)
  assert.match(html, /问题描述/)
  assert.match(html, /工单分类（可选）/)
  assert.match(html, /提交工单/)
  assert.match(html, /取消/)
  assert.match(html, /返回工单列表/)
  assert.match(html, /href="\/tickets"/)
})

test('TicketDetail page renders route id and return action', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(component, '/tickets/42')

  assert.match(html, /工单详情/)
  assert.match(html, /当前工单编号：42/)
  assert.match(html, /返回工单列表/)
  assert.match(html, /暂无工单详情数据/)
})

test('TicketDetail page renders all backend detail fields', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')
  const ticket = {
    id: 42,
    title: '数据库连接失败',
    description: '业务系统无法连接数据库。',
    category: { id: 2, name: '系统问题' },
    status: 'processing',
    priority: 'urgent',
    creator: {
      id: 7,
      username: 'creator',
      email: 'creator@example.com'
    },
    assignee: {
      id: 8,
      username: 'handler',
      email: 'handler@example.com'
    },
    department: { id: 3, name: '研发部' },
    created_at: '2026-11-24T10:00:00+08:00',
    updated_at: '2026-11-24T11:00:00+08:00'
  }

  const html = await renderPage(component, '/tickets/42', (store) => {
    store.currentTicket = ticket
  }, true)

  assert.match(html, /工单 #42/)
  assert.match(html, /数据库连接失败/)
  assert.match(html, /系统问题/)
  assert.match(html, /处理中/)
  assert.match(html, /紧急/)
  assert.match(html, /creator/)
  assert.match(html, /handler/)
  assert.match(html, /研发部/)
  assert.match(html, /业务系统无法连接数据库/)
  assert.match(html, /创建时间/)
  assert.match(html, /更新时间/)
})

test('TicketDetail renders null category and assignee placeholders', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(component, '/tickets/9', (store) => {
    store.currentTicket = {
      id: 9,
      title: '未分类工单',
      description: '描述',
      category: null,
      assignee: null,
      status: 'pending',
      priority: 'medium',
      creator: { id: 1, username: 'creator' },
      department: { id: 2, name: '研发部' },
      created_at: '2026-11-24T10:00:00+08:00',
      updated_at: '2026-11-24T10:00:00+08:00'
    }
  }, true)

  assert.match(html, /未分类/)
  assert.match(html, /暂未分配/)
})

test('TicketDetail lets an admin assign an unassigned pending ticket', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = {
        id: 9,
        title: '待分配工单',
        description: '描述',
        category: null,
        assignee: null,
        status: 'pending',
        priority: 'medium',
        creator: { id: 1, username: 'creator' },
        department: { id: 2, name: '研发部' },
        created_at: '2026-11-24T10:00:00+08:00',
        updated_at: '2026-11-24T10:00:00+08:00'
      }
    },
    true,
    (authStore) => {
      authStore.user = {
        roles: [{ code: 'admin' }],
        department: { id: 2, name: '研发部' },
        permissions: ALL_TICKET_PERMISSIONS
      }
    }
  )

  assert.match(html, /处理人操作/)
  assert.match(html, /分配处理人/)
  assert.doesNotMatch(html, /取消分配/)
})

test('TicketDetail lets a manager reassign their department ticket', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = {
        id: 9,
        title: '处理中工单',
        description: '描述',
        category: null,
        assignee: { id: 8, username: 'handler' },
        status: 'processing',
        priority: 'medium',
        creator: { id: 1, username: 'creator' },
        department: { id: 2, name: '研发部' },
        created_at: '2026-11-24T10:00:00+08:00',
        updated_at: '2026-11-24T10:00:00+08:00'
      }
    },
    true,
    (authStore) => {
      authStore.user = {
        roles: [{ code: 'department_manager' }],
        department: { id: 2, name: '研发部' },
        permissions: ALL_TICKET_PERMISSIONS
      }
    }
  )

  assert.match(html, /重新分配/)
  assert.match(html, /取消分配/)
})

test('TicketDetail hides assignment for other-department managers', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = {
        id: 9,
        title: '其他部门工单',
        description: '描述',
        category: null,
        assignee: null,
        status: 'pending',
        priority: 'medium',
        creator: { id: 1, username: 'creator' },
        department: { id: 2, name: '研发部' },
        created_at: '2026-11-24T10:00:00+08:00',
        updated_at: '2026-11-24T10:00:00+08:00'
      }
    },
    true,
    (authStore) => {
      authStore.user = {
        roles: [{ code: 'department_manager' }],
        department: { id: 3, name: '市场部' },
        permissions: ALL_TICKET_PERMISSIONS
      }
    }
  )

  assert.doesNotMatch(html, /处理人操作/)
  assert.doesNotMatch(html, /分配处理人/)
})

test('TicketDetail hides assignment after a ticket is resolved', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = {
        id: 9,
        title: '已解决工单',
        description: '描述',
        category: null,
        assignee: { id: 8, username: 'handler' },
        status: 'resolved',
        priority: 'medium',
        creator: { id: 1, username: 'creator' },
        department: { id: 2, name: '研发部' },
        created_at: '2026-11-24T10:00:00+08:00',
        updated_at: '2026-11-24T10:00:00+08:00'
      }
    },
    true,
    (authStore) => {
      authStore.user = {
        roles: [{ code: 'admin' }],
        department: { id: 2, name: '研发部' },
        permissions: ALL_TICKET_PERMISSIONS
      }
    }
  )

  assert.doesNotMatch(html, /处理人操作/)
  assert.doesNotMatch(html, /重新分配/)
  assert.doesNotMatch(html, /取消分配/)
})

test('TicketDetail shows assignment for a custom role with permission', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({ status: 'pending' })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 20,
        roles: [{ code: 'custom_assigner' }],
        department: { id: 8, name: '外部协作' },
        permissions: ['tickets.assign_ticket']
      }
    }
  )

  assert.match(html, /处理人操作/)
  assert.match(html, /分配处理人/)
})

test('TicketDetail shows start processing for a pending admin ticket', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({ status: 'pending' })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 1,
        roles: [{ code: 'admin' }],
        department: { id: 2, name: '研发部' },
        permissions: ALL_TICKET_PERMISSIONS
      }
    }
  )

  assert.match(html, /工单处理/)
  assert.match(html, /开始处理/)
  assert.doesNotMatch(html, /标记解决/)
})

test('TicketDetail shows mark resolved for a processing admin ticket', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({ status: 'processing' })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 1,
        roles: [{ code: 'admin' }],
        department: { id: 2, name: '研发部' },
        permissions: ALL_TICKET_PERMISSIONS
      }
    }
  )

  assert.match(html, /工单处理/)
  assert.match(html, /标记解决/)
  assert.doesNotMatch(html, /开始处理/)
})

test('TicketDetail hides processing for resolved and closed tickets', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')
  const auth = {
    id: 1,
    roles: [{ code: 'admin' }],
    department: { id: 2, name: '研发部' },
    permissions: ALL_TICKET_PERMISSIONS
  }

  for (const status of ['resolved', 'closed']) {
    const html = await renderPage(
      component,
      '/tickets/9',
      (store) => {
        store.currentTicket = makeDetailTicket({ status })
      },
      true,
      (authStore) => {
        authStore.user = auth
      }
    )

    assert.doesNotMatch(html, /工单处理/)
    assert.doesNotMatch(html, /开始处理/)
    assert.doesNotMatch(html, /标记解决/)
  }
})

test('TicketDetail lets an assigned ticket handler resolve the ticket', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({
        status: 'processing',
        assignee: { id: 8, username: 'handler' }
      })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 8,
        roles: [{ code: 'ticket_handler' }],
        department: { id: 4, name: '运维部' },
        permissions: HANDLER_TICKET_PERMISSIONS
      }
    }
  )

  assert.match(html, /标记解决/)
})

test('TicketDetail hides processing from a handler assigned elsewhere', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({
        status: 'processing',
        assignee: { id: 10, username: 'other_handler' }
      })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 8,
        roles: [{ code: 'ticket_handler' }],
        department: { id: 4, name: '运维部' },
        permissions: HANDLER_TICKET_PERMISSIONS
      }
    }
  )

  assert.doesNotMatch(html, /工单处理/)
  assert.doesNotMatch(html, /标记解决/)
})

test('TicketDetail shows processing for a custom role with permission', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({ status: 'pending' })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 21,
        roles: [{ code: 'custom_processor' }],
        department: { id: 8, name: '外部协作' },
        permissions: ['tickets.process_ticket']
      }
    }
  )

  assert.match(html, /开始处理/)
})

test('TicketDetail shows close action for a resolved admin ticket', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({ status: 'resolved' })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 1,
        roles: [{ code: 'admin' }],
        department: { id: 2, name: '研发部' },
        permissions: ALL_TICKET_PERMISSIONS
      }
    }
  )

  assert.match(html, /关闭工单/)
  assert.match(html, /关闭后工单进入 closed 状态/)
})

test('TicketDetail hides close action outside the resolved state', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')
  const auth = {
    id: 1,
    roles: [{ code: 'admin' }],
    department: { id: 2, name: '研发部' },
    permissions: ALL_TICKET_PERMISSIONS
  }

  for (const status of ['pending', 'processing', 'closed']) {
    const html = await renderPage(
      component,
      '/tickets/9',
      (store) => {
        store.currentTicket = makeDetailTicket({ status })
      },
      true,
      (authStore) => {
        authStore.user = auth
      }
    )

    assert.doesNotMatch(html, /关闭后工单进入 closed 状态/)
    assert.doesNotMatch(html, />关闭工单</)
  }
})

test('TicketDetail lets a manager close their resolved department ticket', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({
        status: 'resolved',
        department: { id: 2, name: '研发部' }
      })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 2,
        roles: [{ code: 'department_manager' }],
        department: { id: 2, name: '研发部' },
        permissions: ALL_TICKET_PERMISSIONS
      }
    }
  )

  assert.match(html, /关闭工单/)
})

test('TicketDetail hides close from a manager outside the ticket department', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({
        status: 'resolved',
        department: { id: 2, name: '研发部' }
      })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 2,
        roles: [{ code: 'department_manager' }],
        department: { id: 3, name: '市场部' },
        permissions: ALL_TICKET_PERMISSIONS
      }
    }
  )

  assert.doesNotMatch(html, /关闭后工单进入 closed 状态/)
})

test('TicketDetail lets the assigned handler close a resolved ticket', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({
        status: 'resolved',
        assignee: { id: 8, username: 'handler' }
      })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 8,
        roles: [{ code: 'ticket_handler' }],
        department: { id: 4, name: '运维部' },
        permissions: HANDLER_TICKET_PERMISSIONS
      }
    }
  )

  assert.match(html, /关闭工单/)
})

test('TicketDetail hides close from an employee', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({
        status: 'resolved',
        assignee: { id: 9, username: 'employee' }
      })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 9,
        roles: [{ code: 'employee' }],
        department: { id: 2, name: '研发部' },
        permissions: []
      }
    }
  )

  assert.doesNotMatch(html, /关闭后工单进入 closed 状态/)
})

test('TicketDetail shows close for a custom role with permission', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({ status: 'resolved' })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 22,
        roles: [{ code: 'custom_closer' }],
        department: { id: 8, name: '外部协作' },
        permissions: ['tickets.close_ticket']
      }
    }
  )

  assert.match(html, /关闭工单/)
})

test('TicketDetail hides actions when permission codes are absent', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  for (const status of ['pending', 'resolved']) {
    const html = await renderPage(
      component,
      '/tickets/9',
      (store) => {
        store.currentTicket = makeDetailTicket({ status })
      },
      true,
      (authStore) => {
        authStore.user = {
          id: 23,
          roles: [{ code: 'admin' }],
          department: { id: 2, name: '研发部' },
          permissions: []
        }
      }
    )

    assert.doesNotMatch(html, /开始处理/)
    assert.doesNotMatch(html, /关闭工单/)
  }
})

test('TicketDetail shows editing for an admin on a pending ticket', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({ status: 'pending' })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 1,
        roles: [{ code: 'admin' }],
        department: { id: 2, name: '研发部' },
        permissions: ALL_TICKET_PERMISSIONS
      }
    }
  )

  assert.match(html, /工单编辑/)
  assert.match(html, /编辑工单/)
})

test('TicketDetail shows editing for an employee own pending ticket', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({
        status: 'pending',
        creator: { id: 8, username: 'employee' }
      })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 8,
        roles: [{ code: 'employee' }],
        department: { id: 2, name: '研发部' },
        permissions: ['tickets.change_ticket']
      }
    }
  )

  assert.match(html, /编辑工单/)
})

test('TicketDetail hides editing for employee processing ticket', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({
        status: 'processing',
        creator: { id: 8, username: 'employee' }
      })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 8,
        roles: [{ code: 'employee' }],
        department: { id: 2, name: '研发部' },
        permissions: ['tickets.change_ticket']
      }
    }
  )

  assert.doesNotMatch(html, /编辑工单/)
})

test('TicketDetail hides editing for manager outside department', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({
        status: 'pending',
        department: { id: 2, name: '研发部' }
      })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 2,
        roles: [{ code: 'department_manager' }],
        department: { id: 3, name: '市场部' },
        permissions: ['tickets.change_ticket']
      }
    }
  )

  assert.doesNotMatch(html, /编辑工单/)
})

test('TicketDetail hides editing without change permission', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(
    component,
    '/tickets/9',
    (store) => {
      store.currentTicket = makeDetailTicket({ status: 'pending' })
    },
    true,
    (authStore) => {
      authStore.user = {
        id: 1,
        roles: [{ code: 'admin' }],
        department: { id: 2, name: '研发部' },
        permissions: []
      }
    }
  )

  assert.doesNotMatch(html, /编辑工单/)
})

test('TicketDetail page renders loading state', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(component, '/tickets/42', (store) => {
    store.isDetailLoading = true
  })

  assert.match(html, /正在加载工单详情/)
})

test('TicketDetail page renders friendly error and retry', async () => {
  const component = await loadPage('/src/views/tickets/TicketDetail.vue')

  const html = await renderPage(component, '/tickets/42', (store) => {
    store.error = '工单不存在或无权查看'
  })

  assert.match(html, /工单不存在或无权查看/)
  assert.match(html, /重新加载/)
})
