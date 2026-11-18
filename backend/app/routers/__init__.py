"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import cluster as router_cluster
from app.routers import shard as router_shard
from app.routers import merge as router_merge
from app.routers import nodecheck as router_nodecheck
from app.routers import balance as router_balance
from app.routers import resume as router_resume
from app.routers import dashboard as router_dashboard
from app.routers import crawlconf as router_crawlconf
from app.routers import datasource as router_datasource
from app.routers import logparse as router_logparse
from app.routers import ratelimit as router_ratelimit
from app.routers import proxy as router_proxy
from app.routers import robot as router_robot
from app.routers import verify as router_verify
from app.routers import audit as router_audit
from app.routers import storage as router_storage
from app.routers import storage_migration as router_storage_migration

ROUTERS = [router_cluster, router_shard, router_merge, router_nodecheck, router_balance, router_resume, router_dashboard, router_crawlconf, router_datasource, router_logparse, router_ratelimit, router_proxy, router_robot, router_verify, router_audit, router_storage, router_storage_migration]
