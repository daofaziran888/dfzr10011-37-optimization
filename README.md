# 分布式采集调度引擎

面向大规模数据采集团队的分布式采集调度引擎。覆盖采集节点集群管理、任务分片调度、结果聚合归并、节点健康监控、采集流量均衡、断点续采恢复与全局采集看板的完整分布式采集链路。

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/            每个业务模块一个页面
│   ├── src/api/              统一请求封装
│   ├── src/stores/           会话与筛选状态
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/          每个业务模块一组接口
│   ├── app/services/         业务规则与状态流转
│   ├── app/store.py          内存数据仓库
│   ├── app/seed.py           16 个业务模块的示例数据
│   ├── app/seed_migration.py 存储格式迁移窗口与回填记录的示例数据
│   └── tests/                迁移窗口回归测试
├── .gitignore
└── docker-compose.yml
```

## 启动

### 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8000/api/health`

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认监听 `http://127.0.0.1:5173/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8000`。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 采集节点集群 | `cluster` | 集群节点 | 节点编号、节点地址、节点角色 |
| 任务分片调度 | `shard` | 分片任务 | 分片编号、采集计划、分片范围 |
| 结果聚合归并 | `merge` | 聚合任务 | 任务编号、采集计划、分片总数 |
| 节点状态巡检 | `nodecheck` | 巡检记录 | 记录编号、节点编号、CPU使用率 |
| 采集流量均衡 | `balance` | 均衡策略 | 策略编号、负载算法、权重因子 |
| 断点续采恢复 | `resume` | 断点记录 | 断点编号、采集计划、断点位置 |
| 全局采集看板 | `dashboard` | 看板面板 | 面板编号、面板名称、显示指标 |
| 采集配置模板 | `crawlconf` | 配置模板 | 模板编号、模板名称、目标类型 |
| 采集数据源池 | `datasource` | 数据源条目 | 条目编号、数据源名称、源类型 |
| 采集日志解析 | `logparse` | 日志模板 | 模板编号、日志类型、解析规则 |
| 采集频率控制 | `ratelimit` | 频率规则 | 规则编号、目标站点、请求间隔 |
| 采集代理路由 | `proxy` | 代理配置 | 配置编号、代理地址、代理协议 |
| RPA执行记录 | `robot` | 执行记录 | 记录编号、流程模板、执行节点 |
| 采集结果校验 | `verify` | 校验规则 | 规则编号、采集计划、校验类型 |
| 采集操作审计 | `audit` | 审计记录 | 记录编号、操作类型、操作对象 |
| 采集存储分层 | `storage` | 存储策略 | 策略编号、存储层级、文件格式 |
| 存储格式迁移窗口 | `storage-migration` | 迁移批次 | 批次编号、旧格式窗口、新层级文件 |

## 存储格式迁移窗口

`storage-migration` 是采集存储分层和结果聚合归并之间的迁移台账，示例数据在
`backend/app/seed_migration.py`，业务规则在 `backend/app/services/storage_migration.py`。

- 每个采集批次同一时刻只发布一个可读层级：`GET /api/storage-migration/read-manifest`
  里要么是旧格式窗口，要么是新层级文件，不会同时出现。
- 新层级已完成但恢复链仍引用旧格式时，用 `保留旧格式窗口` 或 `立即切换新层级` 二选一：
  保留时清理清单出现「新层级文件 / 延后切换」，立即切换时清理清单出现「旧格式窗口 / 待确认」。
- 回填失败从已迁移文件继续；同一批次并发回填只生成一份迁移结果，重复的历史结果用
  `合并重复结果` 收敛。
- 回填未完成的批次（`STOR-0001`）不会出现在 `GET /api/storage-migration/cleanup-manifest` 里。
- 聚合侧通过 `GET /api/merge/read-layer` 和 `GET /api/merge/{id}/windows` 读取迁移兼容结果。
- 数据库索引、部署环境和本地示例共用 `settings.storage_migration_version`
  （默认 `2026.11.1`，可用 `STORAGE_MIGRATION_VERSION` 覆盖）；回滚时改回
  `2026.10.3` 即可，存量回填记录不删除。
- 存储策略的文件格式、存储层级、保留天数与迁移规则通过
  `GET /api/storage/review` 继续参与迁移结果复核。

回归测试：

```bash
cd backend
python3 -m unittest discover -s tests -v
```

## 约定

- 每个模块的前端页面在 `frontend/src/views/<模块>/index.vue`，后端接口在
  `backend/app/routers/<模块>.py`，业务规则在 `backend/app/services/<模块>.py`。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。

领域：数据工程
子方向：数据采集、爬虫与RPA
