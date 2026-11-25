import { computed, ref } from 'vue'

import {
  hasBusinessPermission,
  hasCustomBusinessRole
} from '../utils/businessPermissions.js'

const ASSIGNABLE_STATUSES = new Set(['pending', 'processing'])
const ADMIN_ROLE_CODE = 'admin'
const DEPARTMENT_MANAGER_ROLE_CODE = 'department_manager'
const ASSIGN_PERMISSION = 'tickets.assign_ticket'

export function canManageTicketAssignment(user, ticket) {
  if (
    !hasBusinessPermission(user, ASSIGN_PERMISSION)
    || !ticket
    || !ASSIGNABLE_STATUSES.has(ticket.status)
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

  if (hasCustomBusinessRole(user)) {
    return true
  }

  return false
}

export function getAssignmentErrorMessage(error) {
  const status = error?.status || error?.response?.status

  if (status === 403) {
    return '无权分配此工单'
  }
  if (status === 404) {
    return '工单不存在或无权操作'
  }
  if (status === 409) {
    return '当前工单状态不允许分配'
  }

  return error?.userMessage
    || error?.response?.data?.message
    || error?.message
    || '工单分配失败，请稍后重试'
}

export function createTicketAssignmentController({
  ticketsStore,
  authStore,
  ticketId,
  currentTicket,
  notifySuccess = () => {},
  notifyError = () => {}
}) {
  const isAssignDialogOpen = ref(false)
  const selectedAssigneeId = ref(null)
  const isAssigning = ref(false)
  const assigneeError = ref('')
  const operationError = ref('')
  let loadedTicketId = null

  const assignees = computed(() => ticketsStore.assignees)
  const isAssigneesLoading = computed(
    () => ticketsStore.isAssigneesLoading
  )
  const canManageAssignment = computed(
    () => canManageTicketAssignment(authStore.user, currentTicket.value)
  )
  const canCancelAssignment = computed(
    () => canManageAssignment.value && currentTicket.value?.assignee != null
  )

  async function loadAssignees(force = false) {
    if (!canManageAssignment.value) {
      return false
    }
    if (ticketsStore.isAssigneesLoading) {
      return false
    }
    if (!force && loadedTicketId === currentTicket.value?.id) {
      return true
    }

    assigneeError.value = ''
    try {
      await ticketsStore.fetchAssignees()
      loadedTicketId = currentTicket.value?.id ?? null
      return true
    } catch (requestError) {
      assigneeError.value = getAssignmentErrorMessage(requestError)
      return false
    }
  }

  async function openAssignDialog() {
    if (!canManageAssignment.value) {
      return false
    }

    selectedAssigneeId.value = (
      currentTicket.value?.assignee?.id ?? null
    )
    isAssignDialogOpen.value = true
    operationError.value = ''
    await loadAssignees()
    return true
  }

  function closeAssignDialog() {
    if (isAssigning.value) {
      return
    }
    isAssignDialogOpen.value = false
  }

  async function refreshTicket() {
    const id = ticketId.value
    if (!id) {
      return false
    }
    try {
      await ticketsStore.fetchTicket(id)
      return true
    } catch {
      operationError.value = '处理人已更新，但工单详情刷新失败'
      notifyError(operationError.value)
      return false
    }
  }

  async function submitAssignment() {
    if (isAssigning.value) {
      return false
    }
    if (!canManageAssignment.value || !ticketId.value) {
      operationError.value = '无权分配此工单'
      notifyError(operationError.value)
      return false
    }
    if (selectedAssigneeId.value == null) {
      operationError.value = '请选择处理人'
      return false
    }

    isAssigning.value = true
    operationError.value = ''
    const previousAssigneeId = currentTicket.value?.assignee?.id ?? null

    try {
      await ticketsStore.assignTicket(
        ticketId.value,
        selectedAssigneeId.value
      )
      const refreshed = await refreshTicket()
      isAssignDialogOpen.value = false
      if (!refreshed) {
        return false
      }
      notifySuccess(
        previousAssigneeId == null
          ? '处理人分配成功'
          : '处理人重新分配成功'
      )
      return true
    } catch (requestError) {
      operationError.value = getAssignmentErrorMessage(requestError)
      notifyError(operationError.value)
      return false
    } finally {
      isAssigning.value = false
    }
  }

  async function cancelAssignment() {
    if (isAssigning.value) {
      return false
    }
    if (!canCancelAssignment.value || !ticketId.value) {
      operationError.value = '无权取消工单分配'
      notifyError(operationError.value)
      return false
    }

    isAssigning.value = true
    operationError.value = ''

    try {
      await ticketsStore.assignTicket(ticketId.value, null)
      const refreshed = await refreshTicket()
      if (!refreshed) {
        return false
      }
      notifySuccess('已取消工单分配')
      return true
    } catch (requestError) {
      operationError.value = getAssignmentErrorMessage(requestError)
      notifyError(operationError.value)
      return false
    } finally {
      isAssigning.value = false
    }
  }

  return {
    assignees,
    isAssigneesLoading,
    isAssignDialogOpen,
    selectedAssigneeId,
    isAssigning,
    assigneeError,
    operationError,
    canManageAssignment,
    canCancelAssignment,
    loadAssignees,
    openAssignDialog,
    closeAssignDialog,
    submitAssignment,
    cancelAssignment
  }
}
