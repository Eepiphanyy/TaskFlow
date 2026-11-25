<script setup>
import { ref } from 'vue'

import { useTicketCreate } from '../../composables/useTicketCreate.js'
const {
  clearFieldError,
  form,
  rules,
  categories,
  isCategoriesLoading,
  isSubmitting,
  submitError,
  categoryLoadError,
  fieldErrors,
  loadCategories,
  submit,
  cancel
} = useTicketCreate()

const formRef = ref()

function handleSubmit() {
  return submit(formRef)
}
</script>

<template>
  <main class="ticket-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">TICKETS</p>
        <h1>创建工单</h1>
        <p class="subtitle">填写问题信息并提交给后端处理。</p>
      </div>
      <router-link :to="{ name: 'ticket-list' }">
        <el-button plain>返回工单列表</el-button>
      </router-link>
    </header>

    <el-card class="form-card" shadow="never">
      <el-alert
        v-if="categoryLoadError"
        :title="categoryLoadError"
        type="warning"
        :closable="false"
        show-icon
        class="form-alert"
      >
        <el-button
          size="small"
          :loading="isCategoriesLoading"
          @click="loadCategories"
        >
          重新加载分类
        </el-button>
      </el-alert>

      <el-alert
        v-if="submitError"
        :title="submitError"
        type="error"
        :closable="false"
        show-icon
        class="form-alert"
      />

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="handleSubmit"
      >
        <el-form-item
          label="工单标题"
          prop="title"
          :error="fieldErrors.title"
        >
          <el-input
            v-model="form.title"
            maxlength="200"
            show-word-limit
            placeholder="请输入工单标题"
            @input="clearFieldError('title')"
          />
        </el-form-item>

        <el-form-item
          label="问题描述"
          prop="description"
          :error="fieldErrors.description"
        >
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="6"
            placeholder="请详细描述问题现象和影响"
            @input="clearFieldError('description')"
          />
        </el-form-item>

        <el-form-item
          label="工单分类（可选）"
          prop="category"
          :error="fieldErrors.category"
        >
          <el-select
            v-model="form.category"
            clearable
            :loading="isCategoriesLoading"
            placeholder="请选择分类"
            @change="clearFieldError('category')"
          >
            <el-option
              v-for="category in categories"
              :key="category.id"
              :label="category.name"
              :value="category.id"
            />
          </el-select>
        </el-form-item>

        <div class="form-actions">
          <el-button
            type="primary"
            native-type="submit"
            :loading="isSubmitting"
            :disabled="isSubmitting"
          >
            {{ isSubmitting ? '正在提交...' : '提交工单' }}
          </el-button>
          <el-button :disabled="isSubmitting" @click="cancel">
            取消
          </el-button>
        </div>
      </el-form>
    </el-card>
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

.form-card {
  max-width: 1120px;
  margin: 0 auto;
}

.form-alert {
  margin-bottom: 22px;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

@media (max-width: 640px) {
  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
