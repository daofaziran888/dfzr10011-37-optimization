"""存储格式迁移窗口的回归测试。

运行：cd backend && python3 -m unittest discover -s tests -v
测试直接操作内存仓库，每个用例前用 seed 重建数据，避免相互影响。
"""
from __future__ import annotations

import copy
import threading
import unittest

from app.config import settings
from app.seed import SEED_ROWS
from app.seed_migration import STORAGE_MIGRATION_SEED
from app.services.storage_migration import SWITCH_IMMEDIATE, SWITCH_KEEP_OLD, service
from app.store import store


class MigrationWindowTestCase(unittest.TestCase):
    def setUp(self) -> None:
        seed = {**SEED_ROWS, **STORAGE_MIGRATION_SEED}
        store._tables = {name: copy.deepcopy(rows) for name, rows in seed.items()}

    # ------------------------------------------------------------ helpers

    def _read_layers(self, batch: str) -> list[str]:
        return [
            item["读取层级"]
            for item in service.read_manifest()["items"]
            if item["批次编号"] == batch
        ]

    def _cleanup_for(self, batch: str) -> list[dict]:
        return [
            item for item in service.cleanup_manifest()["items"]
            if item["批次编号"] == batch
        ]

    def _completed_results(self, batch: str) -> list[str]:
        return [
            item["结果文件"]
            for item in service.list_backfills(batch)["items"]
            if item["status"] == "回填完成"
        ]

    # -------------------------------------------------------------- tests

    def test_each_batch_publishes_at_most_one_read_layer(self) -> None:
        for row in store.rows("storage_migration"):
            batch = row["批次编号"]
            layers = self._read_layers(batch)
            self.assertLessEqual(len(layers), 1, f"{batch} 发布了多个可读层级")
            description = service.get_window(batch)
            self.assertLessEqual(description["可读层级数"], 1, f"{batch} 同时可读两个层级")

    def test_read_manifest_never_lists_old_and_new_together(self) -> None:
        for item in service.read_manifest()["items"]:
            old_readable = item["旧格式窗口"]["可读"]
            new_readable = item["新层级文件"]["可读"]
            self.assertFalse(old_readable and new_readable, f"{item['批次编号']} 两个层级同时可读")

    def test_stor_0001_stays_out_of_cleanup_until_backfill_done(self) -> None:
        self.assertEqual(self._cleanup_for("BATCH-0001"), [])
        service.run_action("BATCH-0001", "重试迁移")
        # 迁移完成但回填仍未完成，依然不能进入清理清单。
        self.assertEqual(self._cleanup_for("BATCH-0001"), [])
        service.run_action("BATCH-0001", "重做回填")
        # 回填完成后才按切换选择出现待清理项。
        service.run_action("BATCH-0001", SWITCH_IMMEDIATE)
        cleanup = self._cleanup_for("BATCH-0001")
        self.assertEqual([item["对象类型"] for item in cleanup], ["旧格式窗口"])
        self.assertEqual(cleanup[0]["策略编号"], "STOR-0001")

    def test_backfill_resumes_from_already_migrated_files(self) -> None:
        before = service.get_window("BATCH-0001")
        self.assertEqual(before["已迁移文件数"], 3)
        service.run_action("BATCH-0001", "重试迁移")
        row, message = service.run_action("BATCH-0001", "重做回填")
        self.assertIn("3/10", message)
        record = service.list_backfills("BATCH-0001")["items"][0]
        self.assertEqual(record["恢复起点文件数"], 3)
        self.assertEqual(record["已回填文件数"], 10)
        self.assertEqual(record["尝试次数"], 2)

    def test_backfill_requires_migration_to_finish_first(self) -> None:
        row, message = service.run_action("BATCH-0001", "重做回填")
        self.assertIsNone(row)
        self.assertIn("请先重试迁移", message)

    def test_duplicate_backfill_results_merge_into_one(self) -> None:
        self.assertEqual(len(self._completed_results("BATCH-0003")), 2)
        row, message = service.run_action("BATCH-0003", "合并重复结果")
        self.assertIsNotNone(row)
        self.assertIn("已合并", message)
        results = self._completed_results("BATCH-0003")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], "parquet/plan-0003/2026-11/part-001.parquet")
        self.assertFalse(service.get_window("BATCH-0003")["重复迁移结果"])
        self.assertEqual(len(self._read_layers("BATCH-0003")), 1)

    def test_duplicate_results_block_new_layer_until_merged(self) -> None:
        row, message = service.run_action("BATCH-0003", SWITCH_IMMEDIATE)
        self.assertIsNone(row)
        self.assertIn("合并重复结果", message)

    def test_keep_old_format_keeps_read_on_old_and_defers_new_layer(self) -> None:
        service.run_action("BATCH-0002", SWITCH_KEEP_OLD)
        self.assertEqual(self._read_layers("BATCH-0002"), ["旧格式窗口"])
        item = service.read_manifest()["items"]
        batch_item = next(entry for entry in item if entry["批次编号"] == "BATCH-0002")
        self.assertEqual(batch_item["读取文件"], "raw/json/plan-0002/2026-11.json")
        cleanup = self._cleanup_for("BATCH-0002")
        self.assertEqual([entry["对象类型"] for entry in cleanup], ["新层级文件"])
        self.assertEqual(cleanup[0]["状态"], "延后切换")
        self.assertIn("新层级切换已延后", service.get_window("BATCH-0002")["待办"])

    def test_immediate_switch_reads_new_and_queues_old_cleanup(self) -> None:
        service.run_action("BATCH-0002", SWITCH_IMMEDIATE)
        self.assertEqual(self._read_layers("BATCH-0002"), ["新层级"])
        batch_item = next(
            entry for entry in service.read_manifest()["items"]
            if entry["批次编号"] == "BATCH-0002"
        )
        self.assertEqual(batch_item["读取文件"], "parquet/plan-0002/2026-11/part-001.parquet")
        cleanup = self._cleanup_for("BATCH-0002")
        self.assertEqual([entry["对象类型"] for entry in cleanup], ["旧格式窗口"])
        self.assertEqual(cleanup[0]["状态"], "待确认")
        self.assertFalse(cleanup[0]["可清理"])

    def test_confirm_cleanup_removes_pending_item(self) -> None:
        service.run_action("BATCH-0004", "确认清理旧格式窗口")
        self.assertEqual(self._cleanup_for("BATCH-0004"), [])
        self.assertEqual(self._read_layers("BATCH-0004"), ["新层级"])

    def test_rollback_restores_old_window_and_keeps_backfill(self) -> None:
        backfills_before = service.list_backfills("BATCH-0004")["total"]
        row, message = service.run_action("BATCH-0004", "回滚到旧格式窗口")
        self.assertIsNotNone(row)
        self.assertIn("已回滚", message)
        self.assertEqual(self._read_layers("BATCH-0004"), ["旧格式窗口"])
        self.assertEqual(service.list_backfills("BATCH-0004")["total"], backfills_before)
        cleanup = self._cleanup_for("BATCH-0004")
        self.assertEqual([entry["对象类型"] for entry in cleanup], ["新层级文件"])

    def test_revalidate_rejects_batch_with_two_readable_layers(self) -> None:
        row = service.get_window("BATCH-0002")
        self.assertTrue(row["新层级文件信息"]["可读"] is False)
        # 人为制造双可读，复核必须拦下。
        raw = next(item for item in store.rows("storage_migration") if item["批次编号"] == "BATCH-0002")
        raw["新层级已提交"] = True
        raw["新层级可读"] = True
        result, message = service.run_action("BATCH-0002", "重新校验聚合读取层级")
        self.assertIsNone(result)
        self.assertIn("两个可读层级", message)
        self.assertEqual(self._read_layers("BATCH-0002"), [])

    def test_concurrent_backfill_only_creates_one_result(self) -> None:
        service.run_action("BATCH-0001", "重试迁移")
        row = service._resolve("BATCH-0001")
        errors: list[BaseException] = []

        def worker() -> None:
            try:
                service.backfill(row)
            except BaseException as error:  # noqa: BLE001 - 线程里的异常要带回主线程断言
                errors.append(error)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        results = self._completed_results("BATCH-0001")
        self.assertEqual(len(results), 1, f"并发回填生成了多份结果：{results}")

    def test_version_consistent_across_db_deploy_and_local_sample(self) -> None:
        info = service.version_info()
        self.assertTrue(info["consistent"])
        self.assertEqual(info["version"], settings.storage_migration_version)
        self.assertEqual(info["sources"]["database_index"], info["sources"]["deployment"])
        self.assertEqual(info["sources"]["deployment"], info["sources"]["local_sample"])
        self.assertTrue(info["rollback_supported"])

    def test_compat_results_only_expose_committed_layer(self) -> None:
        payload = service.compat_results()
        self.assertTrue(payload["items"])
        for item in payload["items"]:
            self.assertTrue(item["已提交"])
            self.assertIn(item["读取层级"], ("旧格式窗口", "新层级"))
            self.assertTrue(item["结果文件"])
        # 每个采集批次最多一条迁移兼容结果，重复结果未合并的批次只保留旧格式窗口这一条。
        batches = [item["批次编号"] for item in payload["items"]]
        self.assertEqual(len(batches), len(set(batches)))
        batch3 = next(item for item in payload["items"] if item["批次编号"] == "BATCH-0003")
        self.assertEqual(batch3["读取层级"], "旧格式窗口")
        self.assertEqual(batch3["结果文件"], "raw/json/plan-0003/2026-11.json")

    def test_policy_review_keeps_storage_policy_fields(self) -> None:
        payload = service.policy_review()
        items = {item["策略编号"]: item for item in payload["items"]}
        self.assertEqual(items["STOR-0001"]["复核结论"], "回填未完成，暂不清理")
        for item in items.values():
            for field in ("存储层级", "文件格式", "保留天数", "迁移规则"):
                self.assertTrue(item[field], f"{item['策略编号']} 缺少 {field}")


if __name__ == "__main__":
    unittest.main()
