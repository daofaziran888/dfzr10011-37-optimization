import { createRouter, createWebHistory } from 'vue-router'

import Overview from '@/views/Overview.vue'
const Cluster = () => import('@/views/cluster/index.vue')
const Shard = () => import('@/views/shard/index.vue')
const Merge = () => import('@/views/merge/index.vue')
const Nodecheck = () => import('@/views/nodecheck/index.vue')
const Balance = () => import('@/views/balance/index.vue')
const Resume = () => import('@/views/resume/index.vue')
const Dashboard = () => import('@/views/dashboard/index.vue')
const Crawlconf = () => import('@/views/crawlconf/index.vue')
const Datasource = () => import('@/views/datasource/index.vue')
const Logparse = () => import('@/views/logparse/index.vue')
const Ratelimit = () => import('@/views/ratelimit/index.vue')
const Proxy = () => import('@/views/proxy/index.vue')
const Robot = () => import('@/views/robot/index.vue')
const Verify = () => import('@/views/verify/index.vue')
const Audit = () => import('@/views/audit/index.vue')
const Storage = () => import('@/views/storage/index.vue')
const StorageMigration = () => import('@/views/storage-migration/index.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    { path: '/cluster', name: 'cluster', component: Cluster },
    { path: '/shard', name: 'shard', component: Shard },
    { path: '/merge', name: 'merge', component: Merge },
    { path: '/nodecheck', name: 'nodecheck', component: Nodecheck },
    { path: '/balance', name: 'balance', component: Balance },
    { path: '/resume', name: 'resume', component: Resume },
    { path: '/dashboard', name: 'dashboard', component: Dashboard },
    { path: '/crawlconf', name: 'crawlconf', component: Crawlconf },
    { path: '/datasource', name: 'datasource', component: Datasource },
    { path: '/logparse', name: 'logparse', component: Logparse },
    { path: '/ratelimit', name: 'ratelimit', component: Ratelimit },
    { path: '/proxy', name: 'proxy', component: Proxy },
    { path: '/robot', name: 'robot', component: Robot },
    { path: '/verify', name: 'verify', component: Verify },
    { path: '/audit', name: 'audit', component: Audit },
    { path: '/storage', name: 'storage', component: Storage },
    { path: '/storage-migration', name: 'storage-migration', component: StorageMigration },
  ],
})

export default router
