"""运行配置：端口、跨域、运行环境与存储迁移版本口径。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# 数据库索引、部署环境与本地示例统一使用这一个版本口径。
# 升级时通过 STORAGE_MIGRATION_VERSION 覆盖，回滚时把值改回上一个兼容版本即可。
DEFAULT_STORAGE_MIGRATION_VERSION = "2026.11.1"
PREVIOUS_STORAGE_MIGRATION_VERSION = "2026.10.3"


@dataclass(frozen=True)
class Settings:
    app_name: str = "分布式采集调度引擎"
    env: str = "local"
    port: int = 8000
    storage_migration_version: str = os.environ.get(
        "STORAGE_MIGRATION_VERSION", DEFAULT_STORAGE_MIGRATION_VERSION
    )
    storage_migration_compatible_versions: tuple[str, ...] = (
        PREVIOUS_STORAGE_MIGRATION_VERSION,
        DEFAULT_STORAGE_MIGRATION_VERSION,
    )
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    )
    page_size_default: int = 20
    page_size_max: int = 200


settings = Settings()
