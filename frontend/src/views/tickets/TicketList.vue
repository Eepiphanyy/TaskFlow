<script setup>
import { useTicketList } from '../../composables/useTicketList.js'

const {
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
} = useTicketList()
</script>

<template>
  <main class="ticket-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">TICKETS</p>
        <h1>工单列表</h1>
        <p class="subtitle">查看你有权限访问的工单记录。</p>
      </div>
      <router-link :to="{ name: 'ticket-create' }">
        <el-button type="primary">创建工单</el-button>
      </router-link>
    </header>

    <section class="toolbar">
      <el-form :inline="true" @submit.prevent="handleSearch">
        <el-form-item label="标题搜索">
          <el-input
            v-model="searchQuery"
            clearable
            placeholder="输入工单标题"
            @keyup.enter="handleSearch"
            @clear="handleClearSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            :loading="isLoading"
          >
            搜索
          </el-button>
          <el-button @click="handleClearSearch">清空</el-button>
        </el-form-item>
        <el-form-item label="排序">
          <el-select
            v-model="ordering"
            class="ordering-select"
            @change="handleOrderingChange"
          >
            <el-option label="最新创建" value="-created_at" />
            <el-option label="最早创建" value="created_at" />
            <el-option label="最近更新" value="-updated_at" />
            <el-option label="标题升序" value="title" />
            <el-option label="标题降序" value="-title" />
            <el-option label="优先级" value="priority" />
          </el-select>
        </el-form-item>
      </el-form>
    </section>

    <section class="filter-panel">
      <div class="filter-heading">
        <h2>筛选</h2>
        <p>多个条件按“且”组合，并继续遵守当前账号的数据范围。</p>
      </div>

      <el-alert
        v-if="categoryLoadError"
        :title="categoryLoadError"
        type="warning"
        :closable="false"
        show-icon
        class="filter-alert"
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
        v-if="filterError"
        :title="filterError"
        type="error"
        :closable="false"
        show-icon
        class="filter-alert"
      />

      <el-form class="filter-form" inline>
        <el-form-item label="状态">
          <el-select
            v-model="filterStatus"
            clearable
            placeholder="全部状态"
            class="filter-select"
          >
            <el-option
              v-for="(option, value) in STATUS_OPTIONS"
              :key="value"
              :label="option.label"
              :value="value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="优先级">
          <el-select
            v-model="filterPriority"
            clearable
            placeholder="全部优先级"
            class="filter-select"
          >
            <el-option
              v-for="(option, value) in PRIORITY_OPTIONS"
              :key="value"
              :label="option.label"
              :value="value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="分类">
          <el-select
            v-model="filterCategory"
            clearable
            filterable
            :loading="isCategoriesLoading"
            placeholder="全部分类"
            class="filter-select"
          >
            <el-option
              v-for="category in categories"
              :key="category.id"
              :label="category.name"
              :value="category.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="创建起始">
          <el-date-picker
            v-model="createdAfter"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="起始日期"
            class="filter-date"
          />
        </el-form-item>

        <el-form-item label="创建结束">
          <el-date-picker
            v-model="createdBefore"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="结束日期"
            class="filter-date"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="isLoading"
            @click="handleApplyFilters"
          >
            应用筛选
          </el-button>
          <el-button @click="handleClearFilters">
            清空筛选
          </el-button>
        </el-form-item>
      </el-form>
    </section>

    <el-alert
      v-if="error"
      :title="error"
      type="error"
      :closable="false"
      show-icon
      class="error-alert"
    >
      <el-button size="small" :loading="isLoading" @click="loadTickets">
        重新加载
      </el-button>
    </el-alert>

    <el-card v-if="isLoading" class="content-card" shadow="never">
      <p class="loading-copy">正在加载工单...</p>
      <el-skeleton :rows="5" animated />
    </el-card>

    <el-card
      v-else-if="tickets.length === 0 && !error"
      class="content-card"
      shadow="never"
    >
      <el-empty description="暂无工单数据">
        <router-link :to="{ name: 'ticket-create' }">
          <el-button type="primary">创建第一张工单</el-button>
        </router-link>
      </el-empty>
    </el-card>

    <el-card v-else-if="tickets.length > 0" class="content-card" shadow="never">
      <el-table :data="tickets" row-key="id" stripe>
        <el-table-column prop="id" label="编号" width="90">
          <template #default="{ row }">#{{ row.id }}</template>
        </el-table-column>
        <el-table-column label="标题" min-width="220">
          <template #default="{ row }">
            <el-button link type="primary" @click="openTicket(row)">
              {{ row.title }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="分类" min-width="120">
          <template #default="{ row }">
            {{ row.category?.name || '未分类' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusPresentation(row.status).type">
              {{ getStatusPresentation(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityPresentation(row.priority).type">
              {{ getPriorityPresentation(row.priority).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建人" min-width="130">
          <template #default="{ row }">
            {{ row.creator?.username || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="180">
          <template #default="{ row }">
            {{ formatTicketDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openTicket(row)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        class="pagination"
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        @current-change="handlePageChange"
        @size-change="handlePageSizeChange"
      />
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

.toolbar,
.filter-panel,
.error-alert,
.content-card {
  max-width: 1120px;
  margin: 0 auto;
}

.toolbar {
  margin-bottom: 20px;
  padding: 18px 20px 2px;
  border: 1px solid #e6eaf0;
  border-radius: 12px;
  background: #fff;
}

.filter-panel {
  margin-bottom: 20px;
  padding: 18px 20px 2px;
  border: 1px solid #e6eaf0;
  border-radius: 12px;
  background: #fff;
}

.filter-heading h2 {
  margin: 0;
  color: #172033;
  font-size: 18px;
}

.filter-heading p {
  margin: 6px 0 16px;
  color: #697386;
}

.filter-alert {
  margin-bottom: 16px;
}

.filter-select {
  width: 140px;
}

.filter-date {
  width: 160px;
}

.ordering-select {
  width: 140px;
}

.error-alert {
  margin-bottom: 20px;
}

.loading-copy {
  margin: 0 0 18px;
  color: #697386;
}

.pagination {
  margin-top: 24px;
  justify-content: flex-end;
}

@media (max-width: 640px) {
  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .toolbar {
    padding-right: 14px;
    padding-left: 14px;
  }

  .filter-panel {
    padding-right: 14px;
    padding-left: 14px;
  }

  .filter-select,
  .filter-date {
    width: 100%;
  }

  .ordering-select {
    width: 100%;
  }

  .pagination {
    justify-content: flex-start;
    overflow-x: auto;
  }
}
</style>
