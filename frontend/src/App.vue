<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">分布式采集调度引擎</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向大规模数据采集团队的分布式采集调度引擎。覆盖采集节点集群管理、任务分片调度、结果聚合归并、节点健康监控、采集流量均衡、断点续采恢复与全局采集看板的完整分布式采集链路。</span>
        <span class="head-user">当前值班：{{ store.operator }} · {{ store.shiftLabel }}</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

const navItems = [{ label: "运营概览", path: "/" }, { label: "采集节点集群", path: "/cluster" }, { label: "任务分片调度", path: "/shard" }, { label: "结果聚合归并", path: "/merge" }, { label: "节点状态巡检", path: "/nodecheck" }, { label: "采集流量均衡", path: "/balance" }, { label: "断点续采恢复", path: "/resume" }, { label: "全局采集看板", path: "/dashboard" }, { label: "采集配置模板", path: "/crawlconf" }, { label: "采集数据源池", path: "/datasource" }, { label: "采集日志解析", path: "/logparse" }, { label: "采集频率控制", path: "/ratelimit" }, { label: "采集代理路由", path: "/proxy" }, { label: "RPA执行记录", path: "/robot" }, { label: "采集结果校验", path: "/verify" }, { label: "采集操作审计", path: "/audit" }, { label: "采集存储分层", path: "/storage" }, { label: "存储格式迁移窗口", path: "/storage-migration" }]
</script>
