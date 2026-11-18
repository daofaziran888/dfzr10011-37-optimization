"""存储格式迁移窗口业务规则：迁移重试、回填恢复、读取清单与清理清单。

核心约束：
* 每个采集批次同一时刻只发布一个可读层级，旧格式窗口和新层级不会同时可读；
* 回填失败从已迁移文件继续，幂等键保证并发回填只产生一份迁移结果；
* 新层级已完成但恢复链仍引用旧格式时，必须显式选择「保留旧格式窗口」或
  「立即切换新层级」，两种选择分别反映到读取清单和清理清单；
* 回填未完成的批次（例如 STOR-0001）不会进入清理清单；
* 迁移版本统一取 settings.storage_migration_version，数据库索引、部署环境与
  本地示例共用同一口径。
"""
from __future__ import annotations

import threading
from typing import Any

from app.config import settings
from app.store import store

MIGRATION_MODULE = "storage_migration"
BACKFILL_MODULE = "migration_backfill"

MIGRATION_VERSION = settings.storage_migration_version

SWITCH_UNDECIDED = "未决"
SWITCH_KEEP_OLD = "保留旧格式窗口"
SWITCH_IMMEDIATE = "立即切换新层级"
SWITCH_ROLLED_BACK = "已回滚"
SWITCH_STRATEGIES = (SWITCH_KEEP_OLD, SWITCH_IMMEDIATE)

OLD_WINDOW_OPEN = "开放"
OLD_WINDOW_PENDING = "待确认"
OLD_WINDOW_CLEANED = "已清理"

MIGRATION_STATUS_FAILED = "迁移失败"
MIGRATION_STATUS_DONE = "迁移完成"
BACKFILL_STATUS_FAILED = "回填失败"
BACKFILL_STATUS_DONE = "回填完成"

_BACKFILL_LOCKS: dict[str, threading.Lock] = {}
_BACKFILL_LOCKS_GUARD = threading.Lock()


def _batch_key(value: Any) -> str:
    return str(value or "").strip()


def _backfill_lock(batch: str) -> threading.Lock:
    with _BACKFILL_LOCKS_GUARD:
        lock = _BACKFILL_LOCKS.get(batch)
        if lock is None:
            lock = threading.Lock()
            _BACKFILL_LOCKS[batch] = lock
        return lock


class StorageMigrationService:
    # ---------------------------------------------------------------- 读取

    def _rows(self) -> list[dict[str, Any]]:
        return store.rows(MIGRATION_MODULE)

    def _backfill_rows(self) -> list[dict[str, Any]]:
        return store.rows(BACKFILL_MODULE)

    def _resolve(self, batch_ref: str | int) -> dict[str, Any] | None:
        key = _batch_key(batch_ref)
        if not key:
            return None
        if key.isdigit():
            for row in self._rows():
                if int(row.get("id", 0)) == int(key):
                    return row
        for row in self._rows():
            if _batch_key(row.get("批次编号")) == key:
                return row
            if _batch_key(row.get("采集计划")) == key:
                return row
        return None

    def _backfills_for(self, batch: str) -> list[dict[str, Any]]:
        return [
            row for row in self._backfill_rows()
            if _batch_key(row.get("批次编号")) == batch
        ]

    def _completed_backfills(self, batch: str) -> list[dict[str, Any]]:
        return [
            row for row in self._backfills_for(batch)
            if row.get("status") == BACKFILL_STATUS_DONE
        ]

    def _has_duplicates(self, row: dict[str, Any]) -> bool:
        batch = _batch_key(row.get("批次编号"))
        return bool(row.get("重复迁移结果")) or len(self._completed_backfills(batch)) > 1

    def _resume_references_old(self, row: dict[str, Any]) -> bool:
        """恢复链是否仍引用旧格式窗口：显式标记之外，也按断点位置反查。"""
        old = _batch_key(row.get("旧格式窗口"))
        if old:
            for item in store.rows("resume"):
                position = _batch_key(item.get("断点位置"))
                if position and (position == old or old in position or position in old):
                    return True
        return bool(row.get("恢复链引用旧格式"))

    def _has_unresolved_conflict(self, row: dict[str, Any]) -> bool:
        """新层级已完成、恢复链仍引用旧格式，且还没有做出切换选择。"""
        return bool(
            row.get("新层级文件状态") == "已完成"
            and self._resume_references_old(row)
            and row.get("切换策略") in ("", None, SWITCH_UNDECIDED)
            and not row.get("新层级已提交")
        )

    def _old_readable(self, row: dict[str, Any]) -> bool:
        return bool(row.get("旧格式可读")) and row.get("旧格式窗口状态") != OLD_WINDOW_CLEANED

    def _new_readable(self, row: dict[str, Any]) -> bool:
        # 新层级只有在提交之后才算正式发布，避免「已完成但未提交」被聚合侧读到。
        return bool(row.get("新层级可读")) and bool(row.get("新层级已提交"))

    def _read_layer(self, row: dict[str, Any]) -> str | None:
        # 新层级只有在提交后才算发布；未提交的新层级即使文件已完成也不会被读到。
        old = self._old_readable(row)
        new = self._new_readable(row)
        if old and new:
            # 理论上不应该出现；两个层级都不发布，等待复核。
            return None
        if new:
            return "新层级"
        if old:
            # 重复结果只影响新层级发布，旧格式窗口仍是该批次唯一的已发布层级。
            return "旧格式窗口"
        return None

    def _read_file(self, row: dict[str, Any], layer: str | None) -> str:
        if layer == "新层级":
            return str(row.get("新层级文件") or "")
        if layer == "旧格式窗口":
            return str(row.get("旧格式窗口") or "")
        return ""

    def _pending(self, row: dict[str, Any]) -> list[str]:
        pending: list[str] = []
        if self._has_duplicates(row):
            pending.append("待合并重复结果")
        if row.get("迁移状态") != MIGRATION_STATUS_DONE:
            pending.append("迁移未完成")
        if row.get("回填状态") != BACKFILL_STATUS_DONE:
            pending.append("回填未完成")
        if self._has_unresolved_conflict(row):
            pending.append("待选择切换策略")
        elif (
            row.get("回填状态") == BACKFILL_STATUS_DONE
            and not self._has_duplicates(row)
            and row.get("新层级文件状态") == "已完成"
            and not row.get("新层级已提交")
            and row.get("切换策略") != SWITCH_KEEP_OLD
        ):
            pending.append("待切换新层级")
        elif row.get("切换策略") == SWITCH_KEEP_OLD:
            pending.append("新层级切换已延后")
        if row.get("切换策略") == SWITCH_IMMEDIATE and row.get("旧格式窗口状态") == OLD_WINDOW_PENDING:
            pending.append("旧格式待确认清理")
        return pending

    def _describe(self, row: dict[str, Any]) -> dict[str, Any]:
        layer = self._read_layer(row)
        read_file = self._read_file(row, layer)
        pending = self._pending(row)
        description = dict(row)
        description.update({
            "可读层级数": int(self._old_readable(row)) + int(self._new_readable(row)),
            "读取层级": layer or "",
            "读取文件": read_file,
            "单层级已发布": bool(layer) and not (self._old_readable(row) and self._new_readable(row)),
            "待办": "、".join(pending) if pending else "无",
            "待办项": pending,
            "迁移版本": str(row.get("迁移版本") or MIGRATION_VERSION),
            "旧格式窗口信息": {
                "路径": row.get("旧格式窗口"),
                "格式": row.get("旧格式"),
                "状态": row.get("旧格式窗口状态"),
                "可读": self._old_readable(row),
            },
            "新层级文件信息": {
                "路径": row.get("新层级文件"),
                "格式": row.get("新格式"),
                "状态": row.get("新层级文件状态"),
                "可读": self._new_readable(row),
                "已提交": bool(row.get("新层级已提交")),
            },
        })
        return description

    def list_windows(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = list(self._rows())
        if keyword:
            rows = [
                row for row in rows
                if keyword in _batch_key(row.get("批次编号"))
                or keyword in _batch_key(row.get("采集计划"))
                or keyword in _batch_key(row.get("策略编号"))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._describe(row) for row in rows[start:start + size]], total

    def get_window(self, batch_ref: str | int) -> dict[str, Any] | None:
        row = self._resolve(batch_ref)
        return self._describe(row) if row else None

    def summary(self) -> dict[str, Any]:
        rows = self._rows()
        return {
            "migration_version": MIGRATION_VERSION,
            "total": len(rows),
            "failed": sum(1 for row in rows if row.get("迁移状态") != MIGRATION_STATUS_DONE),
            "backfill_failed": sum(1 for row in rows if row.get("回填状态") != BACKFILL_STATUS_DONE),
            "conflicts": sum(1 for row in rows if self._has_unresolved_conflict(row)),
            "duplicates": sum(1 for row in rows if self._has_duplicates(row)),
            "published": sum(1 for row in rows if self._read_layer(row)),
        }

    # ------------------------------------------------------------ 读取清单

    def read_manifest(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for row in self._rows():
            described = self._describe(row)
            layer = described["读取层级"]
            if layer:
                items.append({
                    "批次编号": row.get("批次编号"),
                    "采集计划": row.get("采集计划"),
                    "策略编号": row.get("策略编号"),
                    "存储层级": row.get("存储层级"),
                    "文件格式": row.get("文件格式"),
                    "保留天数": row.get("保留天数"),
                    "迁移规则": row.get("迁移规则"),
                    "迁移版本": described["迁移版本"],
                    "读取层级": layer,
                    "读取文件": described["读取文件"],
                    "已提交层级": layer,
                    "单层级已发布": described["单层级已发布"],
                    "旧格式窗口": described["旧格式窗口信息"],
                    "新层级文件": described["新层级文件信息"],
                    "复核状态": row.get("复核状态"),
                })
            else:
                blocked.append({
                    "批次编号": row.get("批次编号"),
                    "采集计划": row.get("采集计划"),
                    "策略编号": row.get("策略编号"),
                    "原因": described["待办"],
                    "旧格式窗口": described["旧格式窗口信息"],
                    "新层级文件": described["新层级文件信息"],
                })
        return {
            "migration_version": MIGRATION_VERSION,
            "environment": settings.env,
            "items": items,
            "blocked": blocked,
            "total": len(items),
        }

    # ------------------------------------------------------------ 清理清单

    def cleanup_manifest(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        deferred = 0
        for row in self._rows():
            # STOR-0001 这类回填未完成的批次不得进入清理清单，连占位项都不生成。
            if row.get("回填状态") != BACKFILL_STATUS_DONE or self._has_duplicates(row):
                deferred += 1
                continue
            strategy = row.get("切换策略")
            base = {
                "批次编号": row.get("批次编号"),
                "采集计划": row.get("采集计划"),
                "策略编号": row.get("策略编号"),
                "存储层级": row.get("存储层级"),
                "文件格式": row.get("文件格式"),
                "保留天数": row.get("保留天数"),
                "迁移规则": row.get("迁移规则"),
                "迁移版本": str(row.get("迁移版本") or MIGRATION_VERSION),
            }
            if strategy == SWITCH_IMMEDIATE and row.get("新层级已提交"):
                if row.get("旧格式窗口状态") == OLD_WINDOW_CLEANED:
                    continue
                items.append({
                    **base,
                    "对象类型": "旧格式窗口",
                    "路径": row.get("旧格式窗口"),
                    "状态": OLD_WINDOW_PENDING,
                    "可清理": False,
                    "原因": "已立即切换新层级，旧格式窗口待确认后再清理",
                })
            elif strategy in (SWITCH_KEEP_OLD, SWITCH_ROLLED_BACK):
                items.append({
                    **base,
                    "对象类型": "新层级文件",
                    "路径": row.get("新层级文件"),
                    "状态": "延后切换",
                    "可清理": False,
                    "原因": "保留旧格式窗口，新层级切换延后，暂不清理",
                })
            else:
                deferred += 1
        return {
            "migration_version": MIGRATION_VERSION,
            "environment": settings.env,
            "items": items,
            "total": len(items),
            "deferred": deferred,
        }

    # -------------------------------------------------------- 聚合侧待办

    def aggregation_windows(self) -> dict[str, Any]:
        """聚合侧看到的存储格式迁移窗口待办与迁移兼容结果。"""
        items: list[dict[str, Any]] = []
        for row in self._rows():
            described = self._describe(row)
            layer = described["读取层级"]
            items.append({
                "批次编号": row.get("批次编号"),
                "采集计划": row.get("采集计划"),
                "策略编号": row.get("策略编号"),
                "存储层级": row.get("存储层级"),
                "文件格式": row.get("文件格式"),
                "保留天数": row.get("保留天数"),
                "迁移规则": row.get("迁移规则"),
                "迁移版本": described["迁移版本"],
                "读取层级": layer or "",
                "读取文件": described["读取文件"],
                "待办": described["待办"],
                "待办项": described["待办项"],
                "迁移兼容结果": {
                    "结果文件": described["读取文件"],
                    "已提交层级": layer or "",
                    "单层级已发布": described["单层级已发布"],
                    "旧格式窗口": row.get("旧格式窗口"),
                    "新层级文件": row.get("新层级文件"),
                },
                "复核状态": row.get("复核状态"),
            })
        return {
            "migration_version": MIGRATION_VERSION,
            "environment": settings.env,
            "items": items,
            "total": len(items),
        }

    def compat_results(self) -> dict[str, Any]:
        """迁移兼容结果：只暴露已提交的单一层级文件。"""
        items: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for row in self._rows():
            layer = self._read_layer(row)
            if not layer:
                blocked.append({
                    "批次编号": row.get("批次编号"),
                    "采集计划": row.get("采集计划"),
                    "策略编号": row.get("策略编号"),
                    "待办": "、".join(self._pending(row)),
                })
                continue
            items.append({
                "批次编号": row.get("批次编号"),
                "采集计划": row.get("采集计划"),
                "策略编号": row.get("策略编号"),
                "存储层级": row.get("存储层级"),
                "文件格式": row.get("文件格式"),
                "保留天数": row.get("保留天数"),
                "迁移规则": row.get("迁移规则"),
                "迁移版本": str(row.get("迁移版本") or MIGRATION_VERSION),
                "读取层级": layer,
                "结果文件": self._read_file(row, layer),
                "已提交": True,
                "单层级已发布": not (self._old_readable(row) and self._new_readable(row)),
                "旧格式窗口": row.get("旧格式窗口"),
                "新层级文件": row.get("新层级文件"),
                "复核状态": row.get("复核状态"),
            })
        return {
            "migration_version": MIGRATION_VERSION,
            "environment": settings.env,
            "items": items,
            "blocked": blocked,
            "total": len(items),
        }

    # ------------------------------------------------------------ 策略复核

    def policy_review(self) -> dict[str, Any]:
        windows = self._rows()
        cleanup = self.cleanup_manifest()["items"]
        items: list[dict[str, Any]] = []
        for policy in store.rows("storage"):
            policy_id = _batch_key(policy.get("策略编号"))
            related = [row for row in windows if _batch_key(row.get("策略编号")) == policy_id]
            pending = [
                row for row in related
                if self._has_duplicates(row)
                or self._has_unresolved_conflict(row)
                or row.get("回填状态") != BACKFILL_STATUS_DONE
                or row.get("迁移状态") != MIGRATION_STATUS_DONE
            ]
            cleanup_count = sum(1 for item in cleanup if item.get("策略编号") == policy_id)
            if any(row.get("回填状态") != BACKFILL_STATUS_DONE for row in related):
                conclusion = "回填未完成，暂不清理"
            elif pending or cleanup_count:
                conclusion = "待复核"
            else:
                conclusion = "通过"
            items.append({
                "策略编号": policy_id,
                "存储层级": policy.get("存储层级"),
                "文件格式": policy.get("文件格式"),
                "压缩算法": policy.get("压缩算法"),
                "保留天数": policy.get("保留天数"),
                "迁移规则": policy.get("迁移规则"),
                "清理方式": policy.get("清理方式"),
                "策略状态": policy.get("策略状态"),
                "迁移窗口数": len(related),
                "已发布读层级": sum(1 for row in related if self._read_layer(row)),
                "待复核窗口": len(pending),
                "清理待办数": cleanup_count,
                "复核结论": conclusion,
                "迁移版本": MIGRATION_VERSION,
            })
        return {
            "migration_version": MIGRATION_VERSION,
            "items": items,
            "total": len(items),
        }

    def version_info(self) -> dict[str, Any]:
        versions = {
            "database_index": MIGRATION_VERSION,
            "deployment": MIGRATION_VERSION,
            "local_sample": MIGRATION_VERSION,
        }
        return {
            "version": MIGRATION_VERSION,
            "compatible_versions": list(settings.storage_migration_compatible_versions),
            "environment": settings.env,
            "sources": versions,
            "consistent": len(set(versions.values())) == 1,
            "rollback_supported": True,
            "existing_backfill_retained": True,
        }

    # ------------------------------------------------------------ 回填记录

    def list_backfills(self, batch_ref: str | int | None = None) -> dict[str, Any]:
        rows = list(self._backfill_rows())
        if batch_ref is not None:
            row = self._resolve(batch_ref)
            batch = _batch_key(row.get("批次编号")) if row else _batch_key(batch_ref)
            rows = [item for item in rows if _batch_key(item.get("批次编号")) == batch]
        items = [dict(row) for row in rows]
        return {
            "migration_version": MIGRATION_VERSION,
            "items": items,
            "total": len(items),
        }

    # ------------------------------------------------------------ 动作

    def run_action(
        self,
        batch_ref: str | int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        row = self._resolve(batch_ref)
        if row is None:
            return None, f"迁移窗口 {batch_ref} 不存在或已归档"
        action = str(action or "").strip()
        values = values or {}
        try:
            if action in ("重试迁移", "重试格式迁移", "继续迁移"):
                message = self.retry_migration(row)
            elif action in ("重做回填", "回填", "继续回填"):
                message = self.backfill(row)
            elif action in ("合并重复结果", "去重", "合并回填结果"):
                message = self.reconcile_duplicates(row)
            elif action in ("保留旧格式窗口", "保留旧格式"):
                message = self.choose_switch(row, SWITCH_KEEP_OLD)
            elif action in ("立即切换新层级", "切换新层级", "立即切换"):
                message = self.choose_switch(row, SWITCH_IMMEDIATE)
            elif action in ("回滚到旧格式窗口", "回滚格式迁移", "回滚"):
                message = self.rollback(row)
            elif action in ("复核读取层级", "重新校验聚合读取层级", "复核"):
                message = self.revalidate(row)
            elif action in ("确认清理旧格式窗口", "确认清理"):
                message = self.confirm_cleanup(row)
            else:
                return None, f"动作「{action}」不属于存储格式迁移窗口可执行范围"
        except ValueError as error:
            return None, str(error)
        return self._describe(row), message

    def retry_migration(self, row: dict[str, Any]) -> str:
        if row.get("迁移状态") == MIGRATION_STATUS_DONE:
            return "格式迁移已完成，无需重试"
        start = int(row.get("已迁移文件数") or 0)
        total = int(row.get("文件总数") or 0)
        row["恢复起点文件数"] = start
        row["已迁移文件数"] = total
        row["迁移尝试次数"] = int(row.get("迁移尝试次数") or 0) + 1
        row["迁移状态"] = MIGRATION_STATUS_DONE
        row["新层级文件状态"] = "已完成"
        row["status"] = "迁移完成"
        row["pending"] = True
        row["abnormal"] = row.get("回填状态") != BACKFILL_STATUS_DONE
        row["复核状态"] = "待复核"
        return f"格式迁移已从第 {start + 1} 个文件继续，补齐至 {total}/{total}"

    def _canonical_backfill(self, batch: str) -> dict[str, Any] | None:
        completed = sorted(
            self._completed_backfills(batch),
            key=lambda item: int(item.get("id", 0)),
        )
        return completed[0] if completed else None

    def _merge_backfill_duplicates(self, row: dict[str, Any]) -> int:
        batch = _batch_key(row.get("批次编号"))
        completed = sorted(
            self._completed_backfills(batch),
            key=lambda item: int(item.get("id", 0)),
        )
        if len(completed) <= 1:
            row["重复迁移结果"] = False
            return 0
        canonical = completed[0]
        duplicates = completed[1:]
        rows = self._backfill_rows()
        for duplicate in duplicates:
            if duplicate in rows:
                rows.remove(duplicate)
        canonical["重复"] = False
        canonical["已回填文件数"] = row.get("已迁移文件数") or canonical.get("已回填文件数")
        row["重复迁移结果"] = False
        row["已合并重复结果"] = int(row.get("已合并重复结果") or 0) + len(duplicates)
        row["迁移结果文件"] = canonical.get("结果文件") or row.get("新层级文件")
        if not row.get("新层级已提交"):
            row["新层级可读"] = False
        row["复核状态"] = "待复核"
        return len(duplicates)

    def backfill(self, row: dict[str, Any]) -> str:
        batch = _batch_key(row.get("批次编号"))
        with _backfill_lock(batch):
            completed = self._completed_backfills(batch)
            if len(completed) > 1:
                merged = self._merge_backfill_duplicates(row)
                return f"回填已完成，已合并 {merged} 份重复迁移结果，仅保留一份结果"
            if completed:
                canonical = completed[0]
                row["回填状态"] = BACKFILL_STATUS_DONE
                row["重复迁移结果"] = False
                row["迁移结果文件"] = canonical.get("结果文件") or row.get("新层级文件")
                return f"回填已完成，返回已有迁移结果 {row['迁移结果文件']}（幂等，不重复生成）"

            if row.get("迁移状态") != MIGRATION_STATUS_DONE:
                raise ValueError(
                    f"格式迁移仍停在 {row.get('已迁移文件数') or 0}/{row.get('文件总数') or 0}，"
                    "请先重试迁移从已迁移文件继续"
                )

            total = int(row.get("文件总数") or 0)
            failed = [
                item for item in self._backfills_for(batch)
                if item.get("status") == BACKFILL_STATUS_FAILED
            ]
            # 回填失败重做时从已回填的文件继续，而不是从 0 重新开始。
            if failed:
                failing = sorted(failed, key=lambda item: int(item.get("id", 0)))[0]
                start = int(failing.get("已回填文件数") or 0)
            else:
                failing = None
                start = int(row.get("已回填文件数") or 0)
            result_file = str(row.get("新层级文件") or "")
            if failing is not None:
                record = failing
                record["恢复起点文件数"] = start
                record["已回填文件数"] = total
                record["尝试次数"] = int(record.get("尝试次数") or 0) + 1
                record["status"] = BACKFILL_STATUS_DONE
                record["pending"] = False
                record["abnormal"] = False
                record["结果文件"] = result_file
                record["重复"] = False
                record["迁移版本"] = MIGRATION_VERSION
            else:
                record = {
                    "id": max((int(item.get("id", 0)) for item in self._backfill_rows()), default=0) + 1,
                    "status": BACKFILL_STATUS_DONE,
                    "pending": False,
                    "abnormal": False,
                    "回填编号": f"BF-{batch or 'NEW'}",
                    "批次编号": batch,
                    "采集计划": row.get("采集计划"),
                    "幂等键": f"backfill:{batch}",
                    "已回填文件数": total,
                    "文件总数": total,
                    "恢复起点文件数": start,
                    "尝试次数": 1,
                    "结果文件": result_file,
                    "重复": False,
                    "迁移版本": MIGRATION_VERSION,
                }
                self._backfill_rows().append(record)

            row["回填状态"] = BACKFILL_STATUS_DONE
            row["迁移状态"] = MIGRATION_STATUS_DONE
            row["已迁移文件数"] = total
            row["新层级文件状态"] = "已完成"
            if not row.get("新层级已提交"):
                row["新层级可读"] = False
            row["迁移结果文件"] = result_file
            row["重复迁移结果"] = False
            row["status"] = "待切换"
            row["pending"] = True
            row["abnormal"] = False
            row["复核状态"] = "待复核"
            return (
                f"回填已从已完成的 {start}/{total} 个文件继续，补齐剩余 {max(total - start, 0)} 个文件，"
                f"迁移结果 {result_file}"
            )

    def reconcile_duplicates(self, row: dict[str, Any]) -> str:
        merged = self._merge_backfill_duplicates(row)
        if merged == 0 and not row.get("重复迁移结果"):
            return "当前批次没有重复迁移结果"
        row["status"] = "待切换"
        row["pending"] = True
        row["abnormal"] = False
        row["复核状态"] = "待复核"
        return f"已合并 {merged} 份重复迁移结果，读取清单只保留一份结果文件"

    def _ensure_switchable(self, row: dict[str, Any]) -> None:
        if self._has_duplicates(row):
            raise ValueError("存在重复迁移结果，请先合并重复结果")
        if row.get("回填状态") != BACKFILL_STATUS_DONE:
            raise ValueError("回填未完成，不能切换读取层级")
        if row.get("新层级文件状态") != "已完成":
            raise ValueError("新层级文件尚未完成，不能切换读取层级")

    def choose_switch(self, row: dict[str, Any], strategy: str) -> str:
        if strategy not in SWITCH_STRATEGIES:
            raise ValueError(f"切换策略「{strategy}」不在允许范围内")
        if row.get("新层级已提交") and strategy == SWITCH_IMMEDIATE:
            return "已切换新层级，读取清单显示新层级文件"
        if row.get("新层级已提交") and strategy == SWITCH_KEEP_OLD:
            raise ValueError("新层级已切换，如需保留旧格式窗口请先回滚")
        self._ensure_switchable(row)
        row["切换策略"] = strategy
        if strategy == SWITCH_KEEP_OLD:
            row["旧格式窗口状态"] = OLD_WINDOW_OPEN
            row["旧格式可读"] = True
            row["新层级可读"] = False
            row["新层级已提交"] = False
            row["新层级切换状态"] = "延后切换"
            row["status"] = "保留旧格式窗口"
            message = "已保留旧格式窗口，读取清单显示旧格式窗口，清理清单延后新层级切换"
        else:
            row["旧格式窗口状态"] = OLD_WINDOW_PENDING
            row["旧格式可读"] = False
            row["新层级可读"] = True
            row["新层级已提交"] = True
            row["新层级切换状态"] = "已切换"
            row["status"] = "已切换"
            message = "已立即切换新层级，读取清单显示新层级文件，清理清单出现旧格式待确认项"
        row["pending"] = True
        row["abnormal"] = False
        row["复核状态"] = "通过"
        return message

    def rollback(self, row: dict[str, Any]) -> str:
        if row.get("新层级已提交") is not True:
            raise ValueError("当前批次尚未切换新层级，无需回滚")
        if row.get("旧格式窗口状态") == OLD_WINDOW_CLEANED:
            raise ValueError("旧格式窗口已清理，无法回滚")
        row["旧格式窗口状态"] = OLD_WINDOW_OPEN
        row["旧格式可读"] = True
        row["新层级可读"] = False
        row["新层级已提交"] = False
        row["新层级切换状态"] = "已回滚"
        row["切换策略"] = SWITCH_ROLLED_BACK
        row["status"] = "已回滚"
        row["pending"] = True
        row["abnormal"] = True
        row["复核状态"] = "待复核"
        return "已回滚到旧格式窗口，新层级文件保留，读取清单显示旧格式窗口"

    def revalidate(self, row: dict[str, Any]) -> str:
        old = self._old_readable(row)
        new = self._new_readable(row)
        if old and new:
            row["复核状态"] = "不通过"
            raise ValueError("同一采集批次同时存在两个可读层级，读取清单复核不通过")
        if not old and not new:
            row["复核状态"] = "不通过"
            raise ValueError("当前批次没有可读层级，读取清单复核不通过")
        if self._has_duplicates(row):
            row["复核状态"] = "不通过"
            raise ValueError("存在重复迁移结果，读取清单复核不通过")
        if self._has_unresolved_conflict(row):
            row["复核状态"] = "不通过"
            raise ValueError("新层级已完成但切换策略未决，读取清单复核不通过")
        row["复核状态"] = "通过"
        row["pending"] = True
        return f"聚合读取层级复核通过，唯一读取层级为{self._read_layer(row)}"

    def confirm_cleanup(self, row: dict[str, Any]) -> str:
        if row.get("旧格式窗口状态") != OLD_WINDOW_PENDING:
            raise ValueError("没有待确认清理的旧格式窗口")
        if row.get("切换策略") != SWITCH_IMMEDIATE:
            raise ValueError("当前批次未立即切换新层级，旧格式窗口不能进入清理确认")
        row["旧格式窗口状态"] = OLD_WINDOW_CLEANED
        row["旧格式可读"] = False
        row["pending"] = False
        row["abnormal"] = False
        row["复核状态"] = "通过"
        return "旧格式窗口已确认清理，清理清单移除该待确认项"


service = StorageMigrationService()
