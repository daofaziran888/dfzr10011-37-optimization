<template>
  <section class="page" data-module="storage">
    <header class="page-head">
      <div>
        <h2>采集存储分层管理</h2>
        <p class="page-desc">维护采集存储的分层配置、格式选择与迁移规则，为采集存储分层管理提供可验证的数据工程流程。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记存储策略</button>
        <button class="btn" type="button" @click="exportRows">导出采集存储分层清单</button>
        <RouterLink class="btn" to="/storage-migration">存储格式迁移窗口</RouterLink>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无采集存储分层数据，可先登记存储策略</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条采集存储分层记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <h3 class="panel-title">存储迁移结果复核</h3>
    <p class="panel-hint">
      文件格式、存储层级、保留天数与迁移规则继续参与复核；回填未完成的策略不会进入清理清单。
    </p>
    <table class="data-table">
      <thead>
        <tr>
          <th>策略编号</th>
          <th>存储层级</th>
          <th>文件格式</th>
          <th>保留天数</th>
          <th>迁移规则</th>
          <th>迁移窗口数</th>
          <th>清理待办数</th>
          <th>复核结论</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in reviewRows" :key="String(item['策略编号'])">
          <td>{{ item['策略编号'] }}</td>
          <td>{{ item['存储层级'] }}</td>
          <td>{{ item['文件格式'] }}</td>
          <td>{{ item['保留天数'] }}</td>
          <td>{{ item['迁移规则'] }}</td>
          <td>{{ item['迁移窗口数'] }}</td>
          <td>{{ item['清理待办数'] }}</td>
          <td>{{ item['复核结论'] }}</td>
        </tr>
        <tr v-if="!reviewRows.length">
          <td :colspan="8" class="empty-state">暂无存储迁移结果复核数据</td>
        </tr>
      </tbody>
    </table>
    <footer class="page-foot">
      <span>迁移版本 {{ reviewVersion || '—' }}</span>
      <RouterLink class="link" to="/storage-migration">查看存储格式迁移窗口</RouterLink>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/storage'
const columns = ["策略编号", "存储层级", "文件格式", "压缩算法", "保留天数", "迁移规则", "清理方式", "策略状态"]
const actions = ["启用策略", "暂停策略", "关闭策略"]
const statuses = ["草稿", "已生效", "已暂停", "已关闭"]
const stats = [{"label": "存储策略总数", "value": 0}, {"label": "已生效策略", "value": 0}, {"label": "已暂停策略", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const reviewRows = ref<Row[]>([])
const reviewVersion = ref('')

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '存储策略登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('采集存储分层动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '采集存储分层操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('存储策略列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await reloadReview()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '采集存储分层列表读取失败'
  }
}

async function reloadReview() {
  try {
    const payload = await fetchJson<Row>(`${ENDPOINT}/review`)
    reviewRows.value = payload.items ?? []
    reviewVersion.value = payload.migration_version ?? ''
  } catch {
    reviewRows.value = []
  }
}

onMounted(reload)
</script>
