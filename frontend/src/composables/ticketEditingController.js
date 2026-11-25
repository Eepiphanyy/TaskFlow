import { computed, reactive, ref } from 'vue'

import { createTicketRules } from './ticketCreateController.js'
import {
  hasBusinessPermission
} from '../utils/businessPermissions.js'

const EDIT_PERMISSION = 'tickets.change_ticket'
const EDITABLE_STATUSES = new Set(['pending', 'processing'])
const ADMIN_ROLE_CODE = 'admin'
const DEPARTMENT_MANAGER_ROLE_CODE = 'department_manager'
const EMPLOYEE_ROLE_CODE = 'employee'

export function canEditTicket(user, ticket) {
  if (
    !hasBusinessPermission(user, EDIT_PERMISSION)
    || !ticket
    || !EDITABLE_STATUSES.has(ticket.status)
  ) {
    return false
  }

  const roleCodes = new Set(
    (user?.roles || []).map((role) => role.code)
  )
  if (roleCodes.has(ADMIN_ROLE_CODE)) {
    return true
  }

  if (
    roleCodes.has(DEPARTMENT_MANAGER_ROLE_CODE)
    && user?.department?.id != null
    && ticket.department?.id === user.department.id
  ) {
    return true
  }

  return (
    roleCodes.has(EMPLOYEE_ROLE_CODE)
    && ticket.status === 'pending'
    && user?.id != null
    && ticket.creator?.id === user.id
  )
}

export function getEditingErrorMessage(error) {
  const status = error?.status || error?.response?.status

  if (status === 403) {
    return '无权编辑此工单'
  }
  if (status === 404) {
    return '工单不存在或无权编辑'
  }
  if (status === 409) {
    return '当前工单状态或角色不允许编辑'
  }

  return error?.userMessage
    || error?.response?.data?.message
    || error?.message
    || '工单编辑失败，请稍后重试'
}

function getFieldError(error, field) {
  const value = error?.response?.data?.[field]
  if (Array.isArray(value)) {
    return value[0] ? String(value[0]) : ''
  }
  return typeof value === 'string' ? value : ''
}

export function createTicketEditingController({
  ticketsStore,
  authStore,
  ticketId,
  currentTicket,
  notifySuccess = () => {},
  notifyWarning = () => {},
  notifyError = () => {}
}) {
  const isEditDialogOpen = ref(false)
  const isSaving = ref(false)
  const categoryLoadError = ref('')
  const saveError = ref('')
  const form = reactive({
    title: '',
    description: '',
    category: null
  })
  const fieldErrors = reactive({
    title: '',
    description: '',
    category: ''
  })

  const categories = computed(() => ticketsStore.categories)
  const isCategoriesLoading = computed(
    () => ticketsStore.isCategoriesLoading
  )
  const canEdit = computed(
    () => canEditTicket(authStore.user, currentTicket.value)
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
      categoryLoadError.value = getEditingErrorMessage(requestError)
      return false
    }
  }

  async function openEditDialog() {
    if (!canEdit.value) {
      return false
    }

    form.title = currentTicket.value?.title || ''
    form.description = currentTicket.value?.description || ''
    form.category = currentTicket.value?.category?.id ?? null
    saveError.value = ''
    clearFieldErrors()
    isEditDialogOpen.value = true
    await loadCategories()
    return true
  }

  function closeEditDialog() {
    if (isSaving.value) {
      return
    }
    isEditDialogOpen.value = false
  }

  async function refreshTicket() {
    if (!ticketId.value) {
      return false
    }

    try {
      await ticketsStore.fetchTicket(ticketId.value)
      return true
    } catch {
      saveError.value = '工单已更新，但详情刷新失败，请重新加载'
      notifyWarning(saveError.value)
      return false
    }
  }

  async function submit(formRef) {
    if (isSaving.value) {
      return false
    }
    if (!canEdit.value || !ticketId.value) {
      saveError.value = '无权编辑此工单'
      notifyError(saveError.value)
      return false
    }

    isSaving.value = true
    saveError.value = ''
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

      await ticketsStore.updateTicket(ticketId.value, {
        title: form.title.trim(),
        description: form.description.trim(),
        category: form.category ?? null
      })
      const refreshed = await refreshTicket()
      isEditDialogOpen.value = false
      if (!refreshed) {
        return false
      }

      notifySuccess('工单编辑成功')
      return true
    } catch (requestError) {
      fieldErrors.title = getFieldError(requestError, 'title')
      fieldErrors.description = getFieldError(
        requestError,
        'description'
      )
      fieldErrors.category = getFieldError(
        requestError,
        'category'
      )
      saveError.value = getEditingErrorMessage(requestError)
      notifyError(saveError.value)
      return false
    } finally {
      isSaving.value = false
    }
  }

  return {
    form,
    rules: createTicketRules,
    categories,
    isCategoriesLoading,
    isEditDialogOpen,
    isSaving,
    categoryLoadError,
    saveError,
    fieldErrors,
    canEdit,
    clearFieldError,
    loadCategories,
    openEditDialog,
    closeEditDialog,
    submit
  }
}
