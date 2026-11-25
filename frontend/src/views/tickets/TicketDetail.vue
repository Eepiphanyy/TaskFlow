<script setup>
import { ref } from 'vue'

import {
  formatTicketDateTime,
  getPriorityPresentation,
  getStatusPresentation
} from '../../composables/ticketListController.js'
import { useTicketAssignment } from '../../composables/useTicketAssignment.js'
import { useTicketClosing } from '../../composables/useTicketClosing.js'
import { useTicketDetail } from '../../composables/useTicketDetail.js'
import { useTicketEditing } from '../../composables/useTicketEditing.js'
import { useTicketProcessing } from '../../composables/useTicketProcessing.js'

const editFormRef = ref()

const {
  ticketId,
  currentTicket,
  isDetailLoading,
  error,
  retry,
  returnToList
} = useTicketDetail()

const {
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
} = useTicketAssignment({
  ticketId,
  currentTicket
})

const {
  isProcessing,
  processError,
  canProcess,
  processActionLabel,
  processCurrentTicket
} = useTicketProcessing({
  ticketId,
  currentTicket
})

const {
  isClosing,
  closeError,
  closeErrorType,
  canClose,
  closeCurrentTicket
} = useTicketClosing({
  ticketId,
  currentTicket
})

const {
  form: editForm,
  rules: editRules,
  categories: editCategories,
  isCategoriesLoading: isEditCategoriesLoading,
  isEditDialogOpen,
  isSaving: isSavingEdit,
  categoryLoadError: editCategoryLoadError,
  saveError: editSaveError,
  fieldErrors: editFieldErrors,
  canEdit,
  clearFieldError,
  loadCategories: loadEditCategories,
  openEditDialog,
  closeEditDialog,
  submit: submitEditForm
} = useTicketEditing({
  ticketId,
  currentTicket
})

function handleEditSubmit() {
  return submitEditForm(editFormRef)
}
</script>

<template>
  <main class="ticket-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">TICKETS</p>
        <h1>工单详情</h1>
        <p class="subtitle">当前工单编号：{{ ticketId }}</p>
      </div>
      <el-button plain @click="returnToList">返回工单列表</el-button>
    </header>

    <el-alert
      v-if="error"
      :title="error"
      type="error"
      :closable="false"
      show-icon
      class="error-alert"
    >
      <el-button
        v-if="ticketId"
        size="small"
        :loading="isDetailLoading"
        @click="retry"
      >
        重新加载
      </el-button>
    </el-alert>

    <el-card v-if="isDetailLoading" class="detail-card" shadow="never">
      <p class="loading-copy">正在加载工单详情...</p>
      <el-skeleton :rows="6" animated />
    </el-card>

    <el-card
      v-else-if="currentTicket"
      class="detail-card"
      shadow="never"
    >
      <div class="detail-heading">
        <div>
          <p class="ticket-number">工单 #{{ currentTicket.id }}</p>
          <h2>{{ currentTicket.title }}</h2>
        </div>
        <div class="tag-row">
          <el-tag :type="getStatusPresentation(currentTicket.status).type">
            {{ getStatusPresentation(currentTicket.status).label }}
          </el-tag>
          <el-tag
            :type="getPriorityPresentation(currentTicket.priority).type"
          >
            {{ getPriorityPresentation(currentTicket.priority).label }}
          </el-tag>
        </div>
      </div>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="工单编号">
          {{ currentTicket.id }}
        </el-descriptions-item>
        <el-descriptions-item label="工单分类">
          {{ currentTicket.category?.name || '未分类' }}
        </el-descriptions-item>
        <el-descriptions-item label="创建人">
          {{ currentTicket.creator?.username || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="当前处理人">
          {{ currentTicket.assignee?.username || '暂未分配' }}
        </el-descriptions-item>
        <el-descriptions-item
          v-if="currentTicket.assignee?.department"
          label="处理人所属部门"
        >
          {{ currentTicket.assignee.department.name }}
        </el-descriptions-item>
        <el-descriptions-item label="所属部门">
          {{ currentTicket.department?.name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ formatTicketDateTime(currentTicket.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">
          {{ formatTicketDateTime(currentTicket.updated_at) }}
        </el-descriptions-item>
      </el-descriptions>

      <section class="description-section">
        <h3>问题描述</h3>
        <p>{{ currentTicket.description }}</p>
      </section>

      <el-alert
        v-if="operationError"
        :title="operationError"
        type="error"
        :closable="false"
        show-icon
        class="operation-alert"
      />

      <el-alert
        v-if="processError"
        :title="processError"
        type="error"
        :closable="false"
        show-icon
        class="operation-alert"
      />

      <el-alert
        v-if="closeError"
        :title="closeError"
        :type="closeErrorType"
        :closable="false"
        show-icon
        class="operation-alert"
      />

      <el-alert
        v-if="editSaveError && !isEditDialogOpen"
        :title="editSaveError"
        type="error"
        :closable="false"
        show-icon
        class="operation-alert"
      />

      <section
        v-if="canEdit"
        class="editing-section"
      >
        <div>
          <h3>工单编辑</h3>
          <p>可修改标题、描述和分类，归属与状态字段保持不变。</p>
        </div>
        <el-button
          plain
          type="primary"
          :disabled="isSavingEdit"
          @click="openEditDialog"
        >
          编辑工单
        </el-button>
      </section>

      <section
        v-if="canProcess"
        class="processing-section"
      >
        <div>
          <h3>工单处理</h3>
          <p>操作后将由后端重新校验权限、Scope 和工单状态。</p>
        </div>
        <el-button
          type="primary"
          :loading="isProcessing"
          :disabled="isProcessing"
          @click="processCurrentTicket"
        >
          {{ processActionLabel }}
        </el-button>
      </section>

      <section
        v-if="canClose"
        class="closing-section"
      >
        <div>
          <h3>关闭工单</h3>
          <p>关闭后工单进入 closed 状态，不能再重新打开。</p>
        </div>
        <el-button
          type="danger"
          :loading="isClosing"
          :disabled="isClosing"
          @click="closeCurrentTicket"
        >
          关闭工单
        </el-button>
      </section>

      <section
        v-if="canManageAssignment"
        class="assignment-section"
      >
        <div>
          <h3>处理人操作</h3>
          <p>
            当前：
            {{ currentTicket.assignee?.username || '暂未分配' }}
          </p>
        </div>
        <div class="assignment-actions">
          <el-button type="primary" @click="openAssignDialog">
            {{ currentTicket.assignee ? '重新分配' : '分配处理人' }}
          </el-button>
          <el-button
            v-if="canCancelAssignment"
            :loading="isAssigning"
            :disabled="isAssigning"
            @click="cancelAssignment"
          >
            取消分配
          </el-button>
        </div>
      </section>
    </el-card>

    <el-card
      v-else-if="!error"
      class="detail-card"
      shadow="never"
    >
      <el-empty description="暂无工单详情数据" />
    </el-card>

    <el-dialog
      v-model="isAssignDialogOpen"
      title="选择处理人"
      width="min(520px, 92vw)"
      :close-on-click-modal="!isAssigning"
      :close-on-press-escape="!isAssigning"
      :show-close="!isAssigning"
    >
      <el-alert
        v-if="assigneeError"
        :title="assigneeError"
        type="error"
        :closable="false"
        show-icon
        class="operation-alert"
      >
        <el-button
          size="small"
          :loading="isAssigneesLoading"
          @click="loadAssignees(true)"
        >
          重新加载处理人
        </el-button>
      </el-alert>

      <el-skeleton
        v-if="isAssigneesLoading"
        :rows="3"
        animated
      />

      <el-empty
        v-else-if="assigneeError"
        description="处理人加载失败"
      />

      <el-empty
        v-else-if="assignees.length === 0"
        description="暂无可分配处理人"
      />

      <el-select
        v-else
        v-model="selectedAssigneeId"
        class="assignee-select"
        filterable
        clearable
        placeholder="请选择处理人"
      >
        <el-option
          v-for="assignee in assignees"
          :key="assignee.id"
          :label="`${assignee.username}（${assignee.department?.name || '未设置部门'}）`"
          :value="assignee.id"
        />
      </el-select>

      <template #footer>
        <el-button
          :disabled="isAssigning"
          @click="closeAssignDialog"
        >
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="isAssigning"
          :disabled="
            isAssigning
            || isAssigneesLoading
            || assignees.length === 0
            || selectedAssigneeId == null
          "
          @click="submitAssignment"
        >
          确认分配
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="isEditDialogOpen"
      title="编辑工单"
      width="min(620px, 94vw)"
      :close-on-click-modal="!isSavingEdit"
      :close-on-press-escape="!isSavingEdit"
      :show-close="!isSavingEdit"
    >
      <el-alert
        v-if="editSaveError"
        :title="editSaveError"
        type="error"
        :closable="false"
        show-icon
        class="operation-alert"
      />

      <el-alert
        v-if="editCategoryLoadError"
        :title="editCategoryLoadError"
        type="warning"
        :closable="false"
        show-icon
        class="operation-alert"
      >
        <el-button
          size="small"
          :loading="isEditCategoriesLoading"
          @click="loadEditCategories"
        >
          重新加载分类
        </el-button>
      </el-alert>

      <el-form
        ref="editFormRef"
        :model="editForm"
        :rules="editRules"
        label-position="top"
        @submit.prevent="handleEditSubmit"
      >
        <el-form-item
          label="工单标题"
          prop="title"
          :error="editFieldErrors.title"
        >
          <el-input
            v-model="editForm.title"
            maxlength="200"
            show-word-limit
            placeholder="请输入工单标题"
            @input="clearFieldError('title')"
          />
        </el-form-item>

        <el-form-item
          label="问题描述"
          prop="description"
          :error="editFieldErrors.description"
        >
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="6"
            placeholder="请详细描述问题现象和影响"
            @input="clearFieldError('description')"
          />
        </el-form-item>

        <el-form-item
          label="工单分类（可选）"
          prop="category"
          :error="editFieldErrors.category"
        >
          <el-select
            v-model="editForm.category"
            clearable
            :loading="isEditCategoriesLoading"
            placeholder="请选择分类"
            @change="clearFieldError('category')"
          >
            <el-option
              v-for="category in editCategories"
              :key="category.id"
              :label="category.name"
              :value="category.id"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button
          :disabled="isSavingEdit"
          @click="closeEditDialog"
        >
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="isSavingEdit"
          :disabled="isSavingEdit"
          @click="handleEditSubmit"
        >
          保存修改
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>

<style scoped>
.ticket-page {
  min-height: 100vh;
  padding: 40px clamp(20px, 5vw, 72px);
  background: #f4f6fa;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  max-width: 1120px;
  margin: 0 auto 28px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #5f7390;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.18em;
}

h1 {
  margin: 0;
  color: #172033;
}

.subtitle {
  margin: 10px 0 0;
  color: #697386;
}

.detail-card,
.error-alert {
  max-width: 1120px;
  margin: 0 auto;
}

.error-alert {
  margin-bottom: 20px;
}

.loading-copy {
  margin: 0 0 18px;
  color: #697386;
}

.detail-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 28px;
}

.ticket-number {
  margin: 0 0 8px;
  color: #697386;
  font-size: 13px;
  font-weight: 600;
}

.detail-heading h2 {
  margin: 0;
  color: #172033;
}

.tag-row {
  display: flex;
  gap: 8px;
}

.description-section {
  margin-top: 28px;
}

.description-section h3 {
  margin: 0 0 12px;
  color: #172033;
}

.description-section p {
  margin: 0;
  color: #475467;
  line-height: 1.8;
  white-space: pre-wrap;
}

.operation-alert {
  margin-top: 24px;
}

.closing-section,
.editing-section,
.processing-section,
.assignment-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-top: 28px;
  padding-top: 24px;
  border-top: 1px solid #e6eaf0;
}

.closing-section h3,
.editing-section h3,
.processing-section h3,
.assignment-section h3 {
  margin: 0 0 8px;
  color: #172033;
}

.closing-section p,
.editing-section p,
.processing-section p,
.assignment-section p {
  margin: 0;
  color: #697386;
}

.assignment-actions {
  display: flex;
  gap: 10px;
}

.assignee-select {
  width: 100%;
}

@media (max-width: 640px) {
  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .detail-heading {
    flex-direction: column;
  }

  .closing-section,
  .editing-section,
  .processing-section,
  .assignment-section {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
