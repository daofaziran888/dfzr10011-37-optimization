<template>
  <section class="page" data-module="merge">
    <header class="page-head">
      <div>
        <h2>结果聚合归并管理</h2>
        <p class="page-desc">维护采集结果的聚合策略、进度追踪与输出管理，为结果聚合归并提供可验证的数据工程流程。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记聚合任务</button>
        <button class="btn" type="button" @click="exportRows">导出结果聚合归并清单</button>
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
          <td :colspan="columns.length + 1" class="empty-state">暂无结果聚合归并数据，可先登记聚合任务</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条结果聚合归并记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <h3 class="panel-title">聚合读取层级（迁移兼容结果）</h3>
    <p class="panel-hint">
      按存储格式迁移窗口复核清单读取：每个采集批次只显示一个已提交层级文件，
      旧格式窗口与新层级不会同时作为有效输出。
    </p>
    <table class="data-table">
      <thead>
        <tr>
          <th>批次编号</th>
          <th>采集计划</th>
          <th>存储层级 / 格式</th>
          <th>读取层级</th>
          <th>结果文件</th>
          <th>迁移版本</th>
          <th>复核状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in readLayers" :key="String(item['批次编号'])">
          <td>{{ item['批次编号'] }}</td>
          <td>{{ item['采集计划'] }}</td>
          <td>{{ item['存储层级'] }} / {{ item['文件格式'] }}</td>
          <td>{{ item['读取层级'] }}</td>
          <td>{{ item['结果文件'] }}</td>
          <td>{{ item['迁移版本'] }}</td>
          <td>{{ item['复核状态'] }}</td>
        </tr>
        <tr v-if="!readLayers.length">
          <td :colspan="7" class="empty-state">暂无已提交的聚合读取层级</td>
        </tr>
      </tbody>
    </table>
    <footer class="page-foot">
      <span>
        迁移版本 {{ readLayerVersion || '—' }} ·
        未就绪批次 {{ readLayerBlocked.length }} 个
      </span>
      <RouterLink class="link" to="/storage-migration">查看存储格式迁移窗口</RouterLink>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/merge'
const columns = ["任务编号", "采集计划", "分片总数", "已归并数", "归并策略", "输出路径", "数据总量", "任务状态"]
const actions = ["启动归并", "重试归并", "归档任务"]
const statuses = ["待归并", "归并中", "已完成", "归并失败"]
const stats = [{"label": "聚合任务总数", "value": 0}, {"label": "归并中任务", "value": 0}, {"label": "已完成任务", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const readLayers = ref<Row[]>([])
const readLayerBlocked = ref<Row[]>([])
const readLayerVersion = ref('')

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '聚合任务登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('结果聚合归并动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '结果聚合归并操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('聚合任务列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await reloadReadLayers()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '结果聚合归并列表读取失败'
  }
}

async function reloadReadLayers() {
  try {
    const payload = await fetchJson<Row>(`${ENDPOINT}/read-layer`)
    readLayers.value = payload.items ?? []
    readLayerBlocked.value = payload.blocked ?? []
    readLayerVersion.value = payload.migration_version ?? ''
  } catch {
    readLayers.value = []
    readLayerBlocked.value = []
  }
}

onMounted(reload)
</script>
