import { computed, onMounted, reactive, ref } from 'vue'

function requiredMessage(label) {
  return `请输入${label}`
}

function createRequiredValidator(label) {
  return (_rule, value, callback) => {
    if (typeof value !== 'string' || !value.trim()) {
      callback(new Error(requiredMessage(label)))
      return
    }
    callback()
  }
}

export const createTicketRules = {
  title: [
    {
      validator: createRequiredValidator('工单标题'),
      trigger: 'blur'
    },
    {
      max: 200,
      message: '工单标题不能超过 200 个字符',
      trigger: 'blur'
    }
  ],
  description: [
    {
      validator: createRequiredValidator('问题描述'),
      trigger: 'blur'
    }
  ]
}

function getRequestErrorMessage(error) {
  return error?.userMessage
    || error?.response?.data?.message
    || error?.message
    || '创建工单失败，请稍后重试'
}

function getFieldError(error, field) {
  const value = error?.response?.data?.[field]
  if (Array.isArray(value)) {
    return value[0] ? String(value[0]) : ''
  }
  return typeof value === 'string' ? value : ''
}

export function isValidTicketId(ticketId) {
  const numericId = Number(ticketId)
  return Number.isInteger(numericId) && numericId > 0
}

export function createTicketCreateController({
  ticketsStore,
  router,
  notifySuccess = () => {},
  notifyError = () => {},
  registerOnMounted = onMounted
}) {
  const form = reactive({
    title: '',
    description: '',
    category: null
  })
  const isSubmitting = ref(false)
  const submitError = ref('')
  const categoryLoadError = ref('')
  const fieldErrors = reactive({
    title: '',
    description: '',
    category: ''
  })

  const categories = computed(() => ticketsStore.categories)
  const isCategoriesLoading = computed(
    () => ticketsStore.isCategoriesLoading
  )

  function clearFieldError(field) {
    if (field in fieldErrors) {
      fieldErrors[field] = ''
    }
  }

  function clearFieldErrors() {
    fieldErrors.title = ''
    fieldErrors.description = ''
    fieldErrors.category = ''
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
      categoryLoadError.value = getRequestErrorMessage(requestError)
      return false
    }
  }

  async function submit(formRef) {
    if (isSubmitting.value) {
      return false
    }

    isSubmitting.value = true
    submitError.value = ''
    clearFieldErrors()

    try {
      if (!formRef?.value) {
        return false
      }

      try {
        await formRef.value.validate()
      } catch {
        return false
      }

      const createdTicket = await ticketsStore.createTicket({
        title: form.title.trim(),
        description: form.description.trim(),
        category: form.category ?? null
      })

      if (!createdTicket || !isValidTicketId(createdTicket.id)) {
        const message = '创建成功，但响应缺少有效工单编号'
        submitError.value = message
        notifyError(message)
        return false
      }

      notifySuccess('工单创建成功')
      await router.push({
        name: 'ticket-detail',
        params: {
          id: createdTicket.id
        }
      })
      return true
    } catch (requestError) {
      fieldErrors.title = getFieldError(requestError, 'title')
      fieldErrors.description = getFieldError(
        requestError,
        'description'
      )
      fieldErrors.category = getFieldError(requestError, 'category')
      submitError.value = getRequestErrorMessage(requestError)
      notifyError(submitError.value)
      return false
    } finally {
      isSubmitting.value = false
    }
  }

  async function cancel() {
    await router.push({ name: 'ticket-list' })
  }

  registerOnMounted(loadCategories)

  return {
    form,
    rules: createTicketRules,
    categories,
    isCategoriesLoading,
    isSubmitting,
    submitError,
    categoryLoadError,
    fieldErrors,
    clearFieldError,
    loadCategories,
    submit,
    cancel
  }
}
