import { computed, onMounted, ref } from 'vue'

export const DEFAULT_ORDERING = '-created_at'
export const DEFAULT_PAGE_SIZE = 10

export const STATUS_OPTIONS = {
  pending: { label: '待处理', type: 'info' },
  processing: { label: '处理中', type: 'warning' },
  resolved: { label: '已解决', type: 'success' },
  closed: { label: '已关闭', type: 'info' }
}

export const PRIORITY_OPTIONS = {
  low: { label: '低', type: 'info' },
  medium: { label: '普通', type: 'info' },
  high: { label: '高', type: 'warning' },
  urgent: { label: '紧急', type: 'danger' }
}

export function getStatusPresentation(status) {
  return STATUS_OPTIONS[status] || { label: status || '-', type: 'info' }
}

export function getPriorityPresentation(priority) {
  return PRIORITY_OPTIONS[priority] || {
    label: priority || '-',
    type: 'info'
  }
}

export function formatTicketDateTime(value) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN', {
    hour12: false
  })
}

export function createTicketListController({
  ticketsStore,
  router,
  registerOnMounted = onMounted
}) {
  const searchQuery = ref('')
  const ordering = ref(DEFAULT_ORDERING)
  const currentPage = ref(1)
  const pageSize = ref(DEFAULT_PAGE_SIZE)
  const filterStatus = ref('')
  const filterPriority = ref('')
  const filterCategory = ref(null)
  const createdAfter = ref('')
  const createdBefore = ref('')
  const categoryLoadError = ref('')
  const filterError = ref('')

  const tickets = computed(() => ticketsStore.tickets)
  const total = computed(() => ticketsStore.pagination?.count || 0)
  const isLoading = computed(() => ticketsStore.isLoading)
  const error = computed(() => ticketsStore.error)
  const categories = computed(() => ticketsStore.categories)
  const isCategoriesLoading = computed(
    () => ticketsStore.isCategoriesLoading
  )

  let inFlightQueryKey = ''

  function buildParams() {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      ordering: ordering.value
    }
    const keyword = searchQuery.value.trim()
    if (keyword) {
      params.search = keyword
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    if (filterPriority.value) {
      params.priority = filterPriority.value
    }
    if (filterCategory.value != null) {
      params.category = filterCategory.value
    }
    if (createdAfter.value) {
      params.created_after = createdAfter.value
    }
    if (createdBefore.value) {
      params.created_before = createdBefore.value
    }
    return params
  }

  async function loadTickets() {
    const params = buildParams()
    const queryKey = JSON.stringify(params)

    if (ticketsStore.isLoading && inFlightQueryKey === queryKey) {
      return false
    }

    inFlightQueryKey = queryKey
    try {
      await ticketsStore.fetchTickets(params)
      return true
    } catch {
      return false
    } finally {
      if (inFlightQueryKey === queryKey) {
        inFlightQueryKey = ''
      }
    }
  }

  async function handleSearch() {
    currentPage.value = 1
    return loadTickets()
  }

  async function handleClearSearch() {
    searchQuery.value = ''
    currentPage.value = 1
    return loadTickets()
  }

  async function handlePageChange(page) {
    currentPage.value = page
    return loadTickets()
  }

  async function handlePageSizeChange(size) {
    pageSize.value = size
    currentPage.value = 1
    return loadTickets()
  }

  async function handleOrderingChange() {
    currentPage.value = 1
    return loadTickets()
  }

  function validateFilters() {
    filterError.value = ''
    if (
      createdAfter.value
      && createdBefore.value
      && createdAfter.value > createdBefore.value
    ) {
      filterError.value = '创建结束日期不能早于开始日期'
      return false
    }
    return true
  }

  async function handleApplyFilters() {
    if (!validateFilters()) {
      return false
    }
    currentPage.value = 1
    return loadTickets()
  }

  async function handleClearFilters() {
    filterStatus.value = ''
    filterPriority.value = ''
    filterCategory.value = null
    createdAfter.value = ''
    createdBefore.value = ''
    filterError.value = ''
    currentPage.value = 1
    return loadTickets()
  }

  async function loadCategories() {
    if (ticketsStore.isCategoriesLoading) {
      return false
    }

    categoryLoadError.value = ''
    try {
      await ticketsStore.fetchCategories()
      return true
    } catch (requestError) {
      categoryLoadError.value = (
        requestError?.userMessage
        || requestError?.response?.data?.message
        || requestError?.message
        || '工单分类加载失败'
      )
      return false
    }
  }

  async function openTicket(ticket) {
    await router.push({
      name: 'ticket-detail',
      params: {
        id: ticket.id
      }
    })
  }

  registerOnMounted(async () => {
    await Promise.all([
      loadTickets(),
      loadCategories()
    ])
  })

  return {
    searchQuery,
    ordering,
    currentPage,
    pageSize,
    filterStatus,
    filterPriority,
    filterCategory,
    createdAfter,
    createdBefore,
    categories,
    isCategoriesLoading,
    categoryLoadError,
    filterError,
    tickets,
    total,
    isLoading,
    error,
    loadTickets,
    handleSearch,
    handleClearSearch,
    handlePageChange,
    handlePageSizeChange,
    handleOrderingChange,
    handleApplyFilters,
    handleClearFilters,
    loadCategories,
    openTicket,
    STATUS_OPTIONS,
    PRIORITY_OPTIONS,
    getStatusPresentation,
    getPriorityPresentation,
    formatTicketDateTime
  }
}
