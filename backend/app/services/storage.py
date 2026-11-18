"""采集存储分层业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.services.storage_migration import service as migration_service
from app.store import store

MODULE = "storage"
REQUIRED_FIELDS = ["策略编号", "存储层级", "文件格式"]
# 文件格式、存储层级、保留天数与迁移规则继续用于存储迁移结果复核。
REVIEW_FIELDS = ["存储层级", "文件格式", "保留天数", "迁移规则"]
STATUS_ORDER = ["草稿", "已生效", "已暂停", "已关闭"]
ACTION_RULES = {"启用策略": "草稿", "暂停策略": "已生效", "关闭策略": "已暂停"}
NEGATIVE_ACTIONS = []


class StorageService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("策略编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def review_entries(self) -> dict[str, Any]:
        """存储迁移结果复核：把迁移窗口的复核结论挂回采集存储分层清单。"""
        review = migration_service.policy_review()
        by_policy = {item["策略编号"]: item for item in review["items"]}
        items: list[dict[str, Any]] = []
        for policy in store.rows(MODULE):
            policy_id = str(policy.get("策略编号") or "")
            outcome = by_policy.get(policy_id, {})
            items.append({
                "策略编号": policy_id,
                **{field: policy.get(field) for field in REVIEW_FIELDS},
                "策略状态": policy.get("status"),
                "迁移窗口数": outcome.get("迁移窗口数", 0),
                "已发布读层级": outcome.get("已发布读层级", 0),
                "清理待办数": outcome.get("清理待办数", 0),
                "复核结论": outcome.get("复核结论", "未关联迁移窗口"),
                "迁移版本": review["migration_version"],
            })
        return {
            "module": MODULE,
            "migration_version": review["migration_version"],
            "items": items,
            "total": len(items),
        }

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"存储策略 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于采集存储分层可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"存储策略已{action}"
