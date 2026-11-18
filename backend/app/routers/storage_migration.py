"""存储格式迁移窗口接口：迁移重试、回填恢复、读取清单与清理清单。

路由只做参数解包，状态流转、幂等与清单口径全部在
app/services/storage_migration.py 里。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult, payload_action
from app.services.storage_migration import service

router = APIRouter(prefix="/api/storage-migration", tags=["存储格式迁移窗口"])

STATUSES = ["迁移失败", "冲突待确认", "复核待处理", "待切换", "保留旧格式窗口", "已切换", "已回滚", "迁移完成"]


@router.get("", response_model=PageResult[dict])
def list_windows(
    keyword: str | None = Query(default=None, description="按批次编号、采集计划或策略编号检索"),
    status: str | None = Query(default=None, description="迁移窗口状态"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按批次编号与状态过滤存储格式迁移窗口；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_windows(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/summary", response_model=dict)
def summary() -> dict[str, Any]:
    """迁移窗口汇总：失败、回填失败、冲突、重复结果与已发布层级数量。"""
    return service.summary()


@router.get("/read-manifest", response_model=dict)
def read_manifest() -> dict[str, Any]:
    """结果聚合读取清单：每个采集批次只出现一个已提交层级文件。"""
    return service.read_manifest()


@router.get("/cleanup-manifest", response_model=dict)
def cleanup_manifest() -> dict[str, Any]:
    """存储清理清单：回填未完成的批次不会出现在这里。"""
    return service.cleanup_manifest()


@router.get("/aggregation", response_model=dict)
def aggregation_windows() -> dict[str, Any]:
    """聚合侧的存储格式迁移窗口待办与迁移兼容结果数据。"""
    return service.aggregation_windows()


@router.get("/compat-results", response_model=dict)
def compat_results() -> dict[str, Any]:
    """迁移兼容结果：只返回已提交的单一层级文件，未就绪批次单独列出。"""
    return service.compat_results()


@router.get("/policy-review", response_model=dict)
def policy_review() -> dict[str, Any]:
    """存储迁移结果复核：文件格式、存储层级、保留天数与迁移规则继续生效。"""
    return service.policy_review()


@router.get("/version", response_model=dict)
def version_info() -> dict[str, Any]:
    """版本口径：数据库索引、部署环境与本地示例共用同一迁移版本。"""
    return service.version_info()


@router.get("/backfills", response_model=dict)
def list_backfills(
    batch: str | None = Query(default=None, description="按批次编号或采集计划过滤回填记录"),
) -> dict[str, Any]:
    """回填记录清单：同一采集批次重复提交时可以看到重复结果与幂等键。"""
    return service.list_backfills(batch)


@router.get("/export")
def export_windows() -> dict[str, Any]:
    """导出存储格式迁移窗口清单。"""
    items, total = service.list_windows(page=1, size=10000)
    return {"module": "storage_migration", "total": total, "items": items}


@router.get("/{batch_ref}", response_model=dict)
def get_window(batch_ref: str) -> dict[str, Any]:
    """读取单个迁移窗口明细；支持批次编号、采集计划或数字 id。"""
    entry = service.get_window(batch_ref)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"迁移窗口 {batch_ref} 不存在或已归档")
    return entry


@router.post("/{batch_ref}/actions", response_model=ActionResult)
def run_action(batch_ref: str, payload: EntryPayload) -> ActionResult:
    """执行重试迁移、重做回填、合并重复结果、选择切换策略、回滚或复核。"""
    action = payload_action(payload)
    entry, message = service.run_action(batch_ref, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
