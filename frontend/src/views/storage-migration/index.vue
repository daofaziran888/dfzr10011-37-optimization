<template>
  <section class="page" data-module="storage-migration">
    <header class="page-head">
      <div>
        <h2>存储格式迁移窗口</h2>
        <p class="page-desc">
          按采集批次核对旧格式窗口与新层级文件：每个批次只发布一个可读层级，
          回填未完成的批次不进入清理清单，迁移兼容结果只暴露已提交的单一层级文件。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="reloadAll">刷新迁移窗口</button>
        <button class="btn primary" type="button" @click="exportWindows">导出迁移窗口清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="filter-bar">
      <label class="filter-item">
        <span>批次 / 采集计划 / 策略</span>
        <input v-model="keyword" placeholder="例如 BATCH-0001" @keyup.enter="reloadAll" />
      </label>
      <button class="btn" type="button" @click="reloadAll">查询</button>
      <button class="btn ghost" type="button" @click="resetKeyword">重置条件</button>
      <span class="version-chip">迁移版本 {{ versionInfo.version || '—' }}</span>
    </div>

    <nav class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <p v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</p>
    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <template v-if="activeTab === 'windows'">
      <table class="data-table">
        <thead>
          <tr>
            <th>批次编号</th>
            <th>采集计划</th>
            <th>策略编号</th>
            <th>存储层级 / 格式</th>
            <th>迁移进度</th>
            <th>回填状态</th>
            <th>旧格式窗口</th>
            <th>新层级文件</th>
            <th>读取层级</th>
            <th>待办</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)">
            <td>{{ row['批次编号'] }}</td>
            <td>{{ row['采集计划'] }}</td>
            <td>{{ row['策略编号'] }}</td>
            <td>{{ row['存储层级'] }} / {{ row['文件格式'] }}</td>
            <td>{{ row['已迁移文件数'] }}/{{ row['文件总数'] }} · {{ row['迁移状态'] }}</td>
            <td>{{ row['回填状态'] }}</td>
            <td>
              {{ row['旧格式窗口'] }}
              <span class="layer-tag" :class="row['旧格式窗口信息']?.可读 ? 'on' : 'off'">
                {{ row['旧格式窗口信息']?.状态 }}
              </span>
            </td>
            <td>
              {{ row['新层级文件'] }}
              <span class="layer-tag" :class="row['新层级文件信息']?.可读 ? 'on' : 'off'">
                {{ row['新层级文件信息']?.状态 }}
              </span>
            </td>
            <td>{{ row['读取层级'] || '未发布' }}</td>
            <td>{{ row['待办'] }}</td>
            <td class="row-actions">
              <button
                v-for="action in availableActions(row)"
                :key="action"
                class="link"
                type="button"
                @click="runAction(row, action)"
              >
                {{ action }}
              </button>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="11" class="empty-state">没有符合条件的存储格式迁移窗口</td>
          </tr>
        </tbody>
      </table>
    </template>

    <template v-else-if="activeTab === 'read'">
      <p class="panel-hint">结果聚合读取清单：每个采集批次只出现一个已提交层级文件，旧格式窗口与新层级不会同时可读。</p>
      <table class="data-table">
        <thead>
          <tr>
            <th>批次编号</th>
            <th>采集计划</th>
            <th>策略编号</th>
            <th>存储层级 / 格式</th>
            <th>读取层级</th>
            <th>读取文件</th>
            <th>单层级已发布</th>
            <th>复核状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in readManifest.items" :key="String(row['批次编号'])">
            <td>{{ row['批次编号'] }}</td>
            <td>{{ row['采集计划'] }}</td>
            <td>{{ row['策略编号'] }}</td>
            <td>{{ row['存储层级'] }} / {{ row['文件格式'] }}</td>
            <td>{{ row['读取层级'] }}</td>
            <td>{{ row['读取文件'] }}</td>
            <td>{{ row['单层级已发布'] ? '是' : '否' }}</td>
            <td>{{ row['复核状态'] }}</td>
          </tr>
          <tr v-if="!readManifest.items.length">
            <td :colspan="8" class="empty-state">读取清单为空</td>
          </tr>
        </tbody>
      </table>
      <h3 class="panel-title">读取清单阻塞项</h3>
      <table class="data-table">
        <thead>
          <tr><th>批次编号</th><th>采集计划</th><th>策略编号</th><th>阻塞原因</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in readManifest.blocked" :key="String(row['批次编号'])">
            <td>{{ row['批次编号'] }}</td>
            <td>{{ row['采集计划'] }}</td>
            <td>{{ row['策略编号'] }}</td>
            <td>{{ row['原因'] }}</td>
          </tr>
          <tr v-if="!readManifest.blocked.length">
            <td :colspan="4" class="empty-state">没有阻塞项，所有批次只发布一个可读层级</td>
          </tr>
        </tbody>
      </table>
    </template>

    <template v-else-if="activeTab === 'cleanup'">
      <p class="panel-hint">
        存储清理清单：回填未完成的批次（如 STOR-0001）不会出现在这里；保留旧格式窗口时清理清单延后新层级切换，
        立即切换新层级时清理清单出现旧格式待确认项。
      </p>
      <table class="data-table">
        <thead>
          <tr>
            <th>批次编号</th>
            <th>策略编号</th>
            <th>对象类型</th>
            <th>路径</th>
            <th>状态</th>
            <th>可清理</th>
            <th>原因</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in cleanupManifest.items" :key="`${row['批次编号']}-${row['对象类型']}`">
            <td>{{ row['批次编号'] }}</td>
            <td>{{ row['策略编号'] }}</td>
            <td>{{ row['对象类型'] }}</td>
            <td>{{ row['路径'] }}</td>
            <td>{{ row['状态'] }}</td>
            <td>{{ row['可清理'] ? '是' : '否' }}</td>
            <td>{{ row['原因'] }}</td>
          </tr>
          <tr v-if="!cleanupManifest.items.length">
            <td :colspan="7" class="empty-state">清理清单为空</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot">
        <span>清理待办 {{ cleanupManifest.total }} 项，另有 {{ cleanupManifest.deferred }} 个批次因回填或重复结果暂缓</span>
      </footer>
    </template>

    <template v-else-if="activeTab === 'backfills'">
      <p class="panel-hint">回填失败从已迁移文件继续，同一批次只保留一份迁移结果；重复提交的幂等键会暴露在这里。</p>
      <table class="data-table">
        <thead>
          <tr>
            <th>回填编号</th>
            <th>批次编号</th>
            <th>幂等键</th>
            <th>已回填 / 文件总数</th>
            <th>尝试次数</th>
            <th>结果文件</th>
            <th>重复</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in backfills.items" :key="String(row['回填编号'])">
            <td>{{ row['回填编号'] }}</td>
            <td>{{ row['批次编号'] }}</td>
            <td>{{ row['幂等键'] }}</td>
            <td>{{ row['已回填文件数'] }}/{{ row['文件总数'] }}</td>
            <td>{{ row['尝试次数'] }}</td>
            <td>{{ row['结果文件'] || '—' }}</td>
            <td>{{ row['重复'] ? '是' : '否' }}</td>
            <td>{{ row['状态'] }}</td>
          </tr>
          <tr v-if="!backfills.items.length">
            <td :colspan="8" class="empty-state">没有回填记录</td>
          </tr>
        </tbody>
      </table>
    </template>

    <template v-else>
      <p class="panel-hint">
        数据库索引、部署环境和本地示例使用同一版本口径；回滚与存量回填都保留，升级时只需要改这一处配置。
      </p>
      <table class="data-table">
        <thead>
          <tr><th>版本来源</th><th>版本号</th></tr>
        </thead>
        <tbody>
          <tr v-for="(value, source) in versionInfo.sources" :key="String(source)">
            <td>{{ sourceLabel(String(source)) }}</td>
            <td>{{ value }}</td>
          </tr>
        </tbody>
      </table>
      <div class="stat-row version-row">
        <article class="stat-card">
          <span class="stat-label">当前迁移版本</span>
          <strong class="stat-value">{{ versionInfo.version }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">兼容版本</span>
          <strong class="stat-value">{{ (versionInfo.compatible_versions || []).join(' / ') }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">版本口径一致</span>
          <strong class="stat-value">{{ versionInfo.consistent ? '是' : '否' }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">回滚 / 存量回填</span>
          <strong class="stat-value">
            {{ versionInfo.rollback_supported ? '支持' : '不支持' }} /
            {{ versionInfo.existing_backfill_retained ? '保留' : '不保留' }}
          </strong>
        </article>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/storage-migration'

const tabs = [
  { key: 'windows', label: '迁移窗口' },
  { key: 'read', label: '聚合读取清单' },
  { key: 'cleanup', label: '清理清单' },
  { key: 'backfills', label: '回填记录' },
  { key: 'version', label: '版本口径' },
]

const activeTab = ref('windows')
const keyword = ref('')
const rows = ref<Row[]>([])
const total = ref(0)
const summary = ref<Row>({})
const readManifest = ref<Row>({ items: [], blocked: [], total: 0 })
const cleanupManifest = ref<Row>({ items: [], total: 0, deferred: 0 })
const backfills = ref<Row>({ items: [], total: 0 })
const versionInfo = ref<Row>({ version: '', sources: {}, compatible_versions: [] })
const noticeMessage = ref('')
const errorMessage = ref('')

const statCards = computed(() => [
  { label: '迁移窗口', value: summary.value.total ?? 0 },
  { label: '迁移失败', value: summary.value.failed ?? 0 },
  { label: '回填失败', value: summary.value.backfill_failed ?? 0 },
  { label: '切换冲突', value: summary.value.conflicts ?? 0 },
  { label: '重复结果', value: summary.value.duplicates ?? 0 },
  { label: '已发布层级', value: summary.value.published ?? 0 },
])

function sourceLabel(source: string) {
  const labels: Record<string, string> = {
    database_index: '数据库索引',
    deployment: '部署环境',
    local_sample: '本地示例',
  }
  return labels[source] ?? source
}

function availableActions(row: Row) {
  const actions: string[] = []
  const readyToSwitch =
    !row['新层级已提交']
    && !row['重复迁移结果']
    && row['回填状态'] === '回填完成'
    && row['新层级文件信息']?.状态 === '已完成'
  if (row['迁移状态'] !== '迁移完成') actions.push('重试迁移')
  if (
    row['回填状态'] !== '回填完成'
    && row['迁移状态'] === '迁移完成'
    && !row['重复迁移结果']
  ) {
    actions.push('重做回填')
  }
  if (row['重复迁移结果']) actions.push('合并重复结果')
  if (readyToSwitch) actions.push('保留旧格式窗口', '立即切换新层级')
  if (row['新层级已提交']) actions.push('回滚到旧格式窗口')
  if (row['旧格式窗口信息']?.状态 === '待确认') actions.push('确认清理旧格式窗口')
  actions.push('重新校验聚合读取层级')
  return actions
}

function resetKeyword() {
  keyword.value = ''
  void reloadAll()
}

function exportWindows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function runAction(row: Row, action: string) {
  noticeMessage.value = ''
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row['批次编号']}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message || '迁移窗口动作未生效'
    } else {
      noticeMessage.value = payload.message || '迁移窗口已更新'
    }
    await reloadAll()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '迁移窗口操作失败'
  }
}

async function reloadAll() {
  errorMessage.value = ''
  const query = keyword.value ? `?keyword=${encodeURIComponent(keyword.value)}` : ''
  try {
    const list = await fetchJson<Row>(`${ENDPOINT}${query}`)
    rows.value = list.items ?? []
    total.value = list.total ?? rows.value.length
    summary.value = await fetchJson<Row>(`${ENDPOINT}/summary`)
    readManifest.value = await fetchJson<Row>(`${ENDPOINT}/read-manifest`)
    cleanupManifest.value = await fetchJson<Row>(`${ENDPOINT}/cleanup-manifest`)
    backfills.value = await fetchJson<Row>(`${ENDPOINT}/backfills`)
    versionInfo.value = await fetchJson<Row>(`${ENDPOINT}/version`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '迁移窗口读取失败'
  }
}

onMounted(reloadAll)
</script>
