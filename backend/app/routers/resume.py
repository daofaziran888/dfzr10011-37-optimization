"""断点续采恢复接口：维护断点记录，覆盖启动恢复、放弃恢复、归档记录等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult, payload_action
from app.services.resume import ResumeService

router = APIRouter(prefix="/api/resume", tags=["断点续采恢复"])

service = ResumeService()

LIST_FIELDS = ["断点编号", "采集计划", "断点位置", "已采集量", "剩余量", "恢复策略", "恢复耗时", "记录状态"]
STATUSES = ["已记录", "恢复中", "已恢复", "已放弃"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按断点编号检索"),
    status: str | None = Query(default=None, description="已记录、恢复中、已恢复、已放弃"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按断点编号与状态过滤断点续采恢复列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id:int}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条断点记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"断点记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条断点记录，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="断点记录已登记", entry=entry)


@router.post("/{entry_id:int}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条断点记录执行启动恢复、放弃恢复、归档记录；不允许的动作会被拦下并说明原因。"""
    action = payload_action(payload)
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出断点续采恢复清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "resume", "total": total, "items": items}
