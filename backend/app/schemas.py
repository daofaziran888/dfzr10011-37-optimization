"""接口出入参模型：列表分页、动作结果与各模块的明细结构。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    """登记或修改一条业务记录时提交的字段集合。

    动作接口两种写法都接受：`{"values": {"action": "..."}}` 或 `{"action": "..."}`，
    前端页面统一用后一种，脚本调用用前一种也不会被拦。
    """

    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None
    action: str | None = None


def payload_action(payload: EntryPayload) -> str:
    """从动作请求体里取出动作名，values 优先，其次顶层字段。"""
    value = payload.values.get("action") or payload.action or ""
    return str(value).strip()



class ClusterEntry(BaseModel):
    """集群节点明细结构。"""

    field_0: str | None = None  # 节点编号
    field_1: str | None = None  # 节点地址
    field_2: str | None = None  # 节点角色
    field_3: str | None = None  # CPU核心
    field_4: str | None = None  # 内存容量
    field_5: str | None = None  # 网络带宽
    field_6: str | None = None  # 心跳时间
    field_7: str | None = None  # 节点状态

class ShardEntry(BaseModel):
    """分片任务明细结构。"""

    field_0: str | None = None  # 分片编号
    field_1: str | None = None  # 采集计划
    field_2: str | None = None  # 分片范围
    field_3: str | None = None  # 分配节点
    field_4: str | None = None  # 开始时间
    field_5: str | None = None  # 结束时间
    field_6: str | None = None  # 重试次数
    field_7: str | None = None  # 分片状态

class MergeEntry(BaseModel):
    """聚合任务明细结构。"""

    field_0: str | None = None  # 任务编号
    field_1: str | None = None  # 采集计划
    field_2: str | None = None  # 分片总数
    field_3: str | None = None  # 已归并数
    field_4: str | None = None  # 归并策略
    field_5: str | None = None  # 输出路径
    field_6: str | None = None  # 数据总量
    field_7: str | None = None  # 任务状态

class NodecheckEntry(BaseModel):
    """巡检记录明细结构。"""

    field_0: str | None = None  # 记录编号
    field_1: str | None = None  # 节点编号
    field_2: str | None = None  # CPU使用率
    field_3: str | None = None  # 内存使用率
    field_4: str | None = None  # 磁盘使用率
    field_5: str | None = None  # 网络延迟
    field_6: str | None = None  # 错误次数
    field_7: str | None = None  # 采样时间

class BalanceEntry(BaseModel):
    """均衡策略明细结构。"""

    field_0: str | None = None  # 策略编号
    field_1: str | None = None  # 负载算法
    field_2: str | None = None  # 权重因子
    field_3: str | None = None  # 最小节点
    field_4: str | None = None  # 最大节点
    field_5: str | None = None  # 扩容阈值
    field_6: str | None = None  # 缩容阈值
    field_7: str | None = None  # 策略状态

class ResumeEntry(BaseModel):
    """断点记录明细结构。"""

    field_0: str | None = None  # 断点编号
    field_1: str | None = None  # 采集计划
    field_2: str | None = None  # 断点位置
    field_3: str | None = None  # 已采集量
    field_4: str | None = None  # 剩余量
    field_5: str | None = None  # 恢复策略
    field_6: str | None = None  # 恢复耗时
    field_7: str | None = None  # 记录状态

class DashboardEntry(BaseModel):
    """看板面板明细结构。"""

    field_0: str | None = None  # 面板编号
    field_1: str | None = None  # 面板名称
    field_2: str | None = None  # 显示指标
    field_3: str | None = None  # 刷新间隔
    field_4: str | None = None  # 告警配置
    field_5: str | None = None  # 数据范围
    field_6: str | None = None  # 创建人
    field_7: str | None = None  # 面板状态

class CrawlconfEntry(BaseModel):
    """配置模板明细结构。"""

    field_0: str | None = None  # 模板编号
    field_1: str | None = None  # 模板名称
    field_2: str | None = None  # 目标类型
    field_3: str | None = None  # 配置参数
    field_4: str | None = None  # 版本号
    field_5: str | None = None  # 使用次数
    field_6: str | None = None  # 创建时间
    field_7: str | None = None  # 模板状态

class DatasourceEntry(BaseModel):
    """数据源条目明细结构。"""

    field_0: str | None = None  # 条目编号
    field_1: str | None = None  # 数据源名称
    field_2: str | None = None  # 源类型
    field_3: str | None = None  # 接入协议
    field_4: str | None = None  # 认证方式
    field_5: str | None = None  # 优先级
    field_6: str | None = None  # 最近采集
    field_7: str | None = None  # 条目状态

class LogparseEntry(BaseModel):
    """日志模板明细结构。"""

    field_0: str | None = None  # 模板编号
    field_1: str | None = None  # 日志类型
    field_2: str | None = None  # 解析规则
    field_3: str | None = None  # 字段提取
    field_4: str | None = None  # 格式化输出
    field_5: str | None = None  # 异常匹配
    field_6: str | None = None  # 应用范围
    field_7: str | None = None  # 模板状态

class RatelimitEntry(BaseModel):
    """频率规则明细结构。"""

    field_0: str | None = None  # 规则编号
    field_1: str | None = None  # 目标站点
    field_2: str | None = None  # 请求间隔
    field_3: str | None = None  # 并发上限
    field_4: str | None = None  # 日配额上限
    field_5: str | None = None  # 优先级调整
    field_6: str | None = None  # 生效时段
    field_7: str | None = None  # 规则状态

class ProxyEntry(BaseModel):
    """代理配置明细结构。"""

    field_0: str | None = None  # 配置编号
    field_1: str | None = None  # 代理地址
    field_2: str | None = None  # 代理协议
    field_3: str | None = None  # 区域标签
    field_4: str | None = None  # 可用比例
    field_5: str | None = None  # 切换阈值
    field_6: str | None = None  # 响应延迟
    field_7: str | None = None  # 配置状态

class RobotEntry(BaseModel):
    """执行记录明细结构。"""

    field_0: str | None = None  # 记录编号
    field_1: str | None = None  # 流程模板
    field_2: str | None = None  # 执行节点
    field_3: str | None = None  # 开始时间
    field_4: str | None = None  # 结束时间
    field_5: str | None = None  # 执行结果
    field_6: str | None = None  # 异常信息
    field_7: str | None = None  # 记录状态

class VerifyEntry(BaseModel):
    """校验规则明细结构。"""

    field_0: str | None = None  # 规则编号
    field_1: str | None = None  # 采集计划
    field_2: str | None = None  # 校验类型
    field_3: str | None = None  # 校验字段
    field_4: str | None = None  # 阈值配置
    field_5: str | None = None  # 不通过动作
    field_6: str | None = None  # 最近校验
    field_7: str | None = None  # 规则状态

class AuditEntry(BaseModel):
    """审计记录明细结构。"""

    field_0: str | None = None  # 记录编号
    field_1: str | None = None  # 操作类型
    field_2: str | None = None  # 操作对象
    field_3: str | None = None  # 操作人
    field_4: str | None = None  # 操作时间
    field_5: str | None = None  # 操作详情
    field_6: str | None = None  # 影响范围
    field_7: str | None = None  # 复核状态

class StorageEntry(BaseModel):
    """存储策略明细结构。"""

    field_0: str | None = None  # 策略编号
    field_1: str | None = None  # 存储层级
    field_2: str | None = None  # 文件格式
    field_3: str | None = None  # 压缩算法
    field_4: str | None = None  # 保留天数
    field_5: str | None = None  # 迁移规则
    field_6: str | None = None  # 清理方式
    field_7: str | None = None  # 策略状态
