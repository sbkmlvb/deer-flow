"""
LangGraph API 数据模型定义

完全兼容 @langchain/langgraph-sdk 的类型定义
参考: langgraph_sdk/schema.py
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ============== 枚举类型 ==============

RunStatus = Literal["pending", "running", "error", "success", "timeout", "interrupted"]
ThreadStatus = Literal["idle", "busy", "interrupted", "error"]
StreamMode = Literal[
    "values",
    "messages",
    "updates",
    "events",
    "tasks",
    "checkpoints",
    "debug",
    "custom",
    "messages-tuple",
]
ThreadStreamMode = Literal["run_modes", "lifecycle", "state_update"]
DisconnectMode = Literal["cancel", "continue"]
MultitaskStrategy = Literal["reject", "interrupt", "rollback", "enqueue"]
OnConflictBehavior = Literal["raise", "do_nothing"]
OnCompletionBehavior = Literal["delete", "keep"]
Durability = Literal["sync", "async", "exit"]
IfNotExists = Literal["create", "reject"]
PruneStrategy = Literal["delete", "keep_latest"]
CancelAction = Literal["interrupt", "rollback"]
BulkCancelRunsStatus = Literal["pending", "running", "all"]
SortOrder = Literal["asc", "desc"]
AssistantSortBy = Literal["assistant_id", "graph_id", "name", "created_at", "updated_at"]
ThreadSortBy = Literal["thread_id", "status", "created_at", "updated_at", "state_updated_at"]
ThreadSelectField = Literal[
    "thread_id",
    "created_at",
    "updated_at",
    "metadata",
    "config",
    "context",
    "status",
    "values",
    "interrupts",
]
AssistantSelectField = Literal[
    "assistant_id",
    "graph_id",
    "name",
    "description",
    "config",
    "context",
    "created_at",
    "updated_at",
    "metadata",
    "version",
]

# ============== 通用模型 ==============


class Config(BaseModel):
    """运行配置"""

    tags: list[str] | None = Field(default=None, description="标签列表")
    recursion_limit: int | None = Field(default=None, description="最大递归次数，默认25")
    configurable: dict[str, Any] | None = Field(default=None, description="运行时可配置参数")


class Checkpoint(BaseModel):
    """检查点"""

    thread_id: str = Field(description="线程ID")
    checkpoint_ns: str = Field(default="", description="检查点命名空间")
    checkpoint_id: str | None = Field(default=None, description="检查点ID")
    checkpoint_map: dict[str, Any] | None = Field(default=None, description="检查点数据映射")


class Interrupt(BaseModel):
    """中断对象"""

    value: Any = Field(description="中断关联的值")
    id: str = Field(description="中断ID")


class Send(BaseModel):
    """发送消息到特定节点"""

    node: str = Field(description="目标节点")
    input: dict[str, Any] | None = Field(default=None, description="输入数据")


class Command(BaseModel):
    """控制命令"""

    goto: str | Send | list[str | Send] | None = Field(default=None, description="跳转目标")
    update: dict[str, Any] | list[tuple[str, Any]] | None = Field(default=None, description="状态更新")
    resume: Any = Field(default=None, description="恢复值")


# ============== Thread 相关模型 ==============


class ThreadCreateRequest(BaseModel):
    """创建线程请求"""

    thread_id: str | None = Field(default=None, description="可选的线程ID")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")
    if_exists: OnConflictBehavior | None = Field(default=None, description="冲突处理")
    supersteps: list[dict[str, Any]] | None = Field(default=None, description="初始超步骤")
    graph_id: str | None = Field(default=None, description="关联的图ID")
    ttl: int | dict[str, Any] | None = Field(default=None, description="TTL配置（分钟）")


class ThreadUpdateRequest(BaseModel):
    """更新线程请求"""

    metadata: dict[str, Any] = Field(description="要合并的元数据")
    ttl: int | dict[str, Any] | None = Field(default=None, description="TTL配置")


class ThreadSearchRequest(BaseModel):
    """搜索线程请求"""

    metadata: dict[str, Any] | None = Field(default=None, description="元数据过滤")
    values: dict[str, Any] | None = Field(default=None, description="状态值过滤")
    ids: list[str] | None = Field(default=None, description="线程ID列表")
    status: ThreadStatus | None = Field(default=None, description="状态过滤")
    limit: int = Field(default=10, description="返回数量限制")
    offset: int = Field(default=0, description="偏移量")
    sort_by: ThreadSortBy | None = Field(default=None, description="排序字段")
    sort_order: SortOrder | None = Field(default=None, description="排序方向")
    select: list[ThreadSelectField] | None = Field(default=None, description="选择返回的字段")
    extract: dict[str, str] | None = Field(default=None, description="提取字段映射")


class ThreadCountRequest(BaseModel):
    """统计线程请求"""

    metadata: dict[str, Any] | None = Field(default=None)
    values: dict[str, Any] | None = Field(default=None)
    status: ThreadStatus | None = Field(default=None)


class ThreadPruneRequest(BaseModel):
    """清理线程请求"""

    thread_ids: list[str] = Field(description="要清理的线程ID列表")
    strategy: PruneStrategy = Field(default="delete", description="清理策略")


class ThreadTask(BaseModel):
    """线程任务"""

    id: str = Field(description="任务ID")
    name: str = Field(description="节点名称")
    error: str | None = Field(default=None, description="错误信息")
    interrupts: list[Interrupt] = Field(default_factory=list, description="中断列表")
    checkpoint: Checkpoint | None = Field(default=None, description="检查点")
    state: dict[str, Any] | None = Field(default=None, description="子图状态")
    result: dict[str, Any] | None = Field(default=None, description="执行结果")


class ThreadState(BaseModel):
    """线程状态"""

    values: list[dict] | dict[str, Any] = Field(description="状态值")
    next: list[str] = Field(default_factory=list, description="下一步要执行的节点")
    checkpoint: Checkpoint = Field(description="当前检查点")
    metadata: dict[str, Any] | None = Field(default=None, description="状态元数据")
    created_at: str | None = Field(default=None, description="创建时间戳")
    parent_checkpoint: Checkpoint | None = Field(default=None, description="父检查点")
    tasks: list[ThreadTask] = Field(default_factory=list, description="待执行任务")
    interrupts: list[Interrupt] = Field(default_factory=list, description="抛出的中断")


class UpdateStateRequest(BaseModel):
    """更新线程状态请求"""

    values: dict[str, Any] | list[dict] | None = Field(default=None, description="要更新的值")
    as_node: str | None = Field(default=None, description="模拟的节点名称")
    checkpoint: Checkpoint | None = Field(default=None, description="检查点")
    checkpoint_id: str | None = Field(default=None, description="检查点ID（已废弃）")


class UpdateStateResponse(BaseModel):
    """更新线程状态响应"""

    checkpoint: Checkpoint = Field(description="更新后的检查点")


class ThreadHistoryRequest(BaseModel):
    """获取线程历史请求"""

    limit: int = Field(default=10, description="最大返回数量")
    before: str | Checkpoint | None = Field(default=None, description="返回此检查点之前的状态")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据过滤")
    checkpoint: Checkpoint | None = Field(default=None, description="子图检查点")


class Thread(BaseModel):
    """线程对象"""

    thread_id: str = Field(description="线程唯一标识")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")
    status: ThreadStatus = Field(default="idle", description="状态")
    values: dict[str, Any] | None = Field(default=None, description="当前状态值")
    interrupts: dict[str, list[dict]] = Field(default_factory=dict, description="中断映射")


# ============== Run 相关模型 ==============


class RunInput(BaseModel):
    """运行输入"""

    messages: list[dict] = Field(default_factory=list, description="消息列表")


class RunCreateRequest(BaseModel):
    """创建运行请求"""

    assistant_id: str = Field(default="lead_agent", description="助手ID")
    input: RunInput | dict[str, Any] | None = Field(default=None, description="输入")
    command: Command | None = Field(default=None, description="控制命令")
    stream_mode: StreamMode | list[StreamMode] | None = Field(default="values", description="流模式")
    stream_subgraphs: bool = Field(default=False, description="是否流式输出子图")
    stream_resumable: bool = Field(default=False, description="是否可恢复")
    metadata: dict[str, Any] | None = Field(default=None, description="运行元数据")
    config: Config | dict[str, Any] | None = Field(default=None, description="配置")
    context: dict[str, Any] | None = Field(default=None, description="静态上下文")
    checkpoint: Checkpoint | None = Field(default=None, description="恢复的检查点")
    checkpoint_id: str | None = Field(default=None, description="恢复的检查点ID")
    checkpoint_during: bool | None = Field(default=None, description="是否运行时检查点（已废弃）")
    interrupt_before: str | list[str] | None = Field(default=None, description="执行前中断的节点")
    interrupt_after: str | list[str] | None = Field(default=None, description="执行后中断的节点")
    feedback_keys: list[str] | None = Field(default=None, description="反馈键")
    on_disconnect: DisconnectMode | None = Field(default=None, description="断开行为")
    webhook: str | None = Field(default=None, description="完成回调URL")
    multitask_strategy: MultitaskStrategy | None = Field(default=None, description="多任务策略")
    if_not_exists: IfNotExists | None = Field(default=None, description="线程不存在时的行为")
    on_completion: OnCompletionBehavior | None = Field(default=None, description="完成后的行为")
    after_seconds: int | None = Field(default=None, description="延迟执行秒数")
    durability: Durability | None = Field(default=None, description="持久化模式")


class RunStreamRequest(RunCreateRequest):
    """流式运行请求"""

    pass


class RunWaitRequest(RunCreateRequest):
    """等待运行请求"""

    raise_error: bool = Field(default=True, description="是否在错误时抛出异常")


class Run(BaseModel):
    """运行对象"""

    run_id: str = Field(description="运行ID")
    thread_id: str = Field(description="线程ID")
    assistant_id: str = Field(description="助手ID")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")
    status: RunStatus = Field(description="状态")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")
    multitask_strategy: MultitaskStrategy | None = Field(default=None, description="多任务策略")
    kwargs: dict[str, Any] | None = Field(default=None, description="运行参数")


# Context 类型别名
Context = dict[str, Any]


class RunListRequest(BaseModel):
    """列出运行请求"""

    limit: int = Field(default=10, description="返回数量限制")
    offset: int = Field(default=0, description="偏移量")
    status: RunStatus | None = Field(default=None, description="状态过滤")


class RunCancelRequest(BaseModel):
    """取消运行请求"""

    wait: bool = Field(default=False, description="是否等待完成")
    action: CancelAction = Field(default="interrupt", description="取消动作")


class BulkCancelRunsRequest(BaseModel):
    """批量取消运行请求"""

    thread_id: str | None = Field(default=None, description="线程ID")
    run_ids: list[str] | None = Field(default=None, description="运行ID列表")
    status: BulkCancelRunsStatus | None = Field(default=None, description="状态过滤")
    action: CancelAction = Field(default="interrupt", description="取消动作")


class JoinStreamRequest(BaseModel):
    """加入运行流请求"""

    stream_mode: StreamMode | list[StreamMode] | None = Field(default=None, description="流模式")
    cancel_on_disconnect: bool = Field(default=False, description="断开时取消")
    last_event_id: str | None = Field(default=None, description="最后事件ID")


# ============== Assistant 相关模型 ==============


class AssistantCreateRequest(BaseModel):
    """创建助手请求"""

    graph_id: str | None = Field(default=None, description="图ID")
    config: Config | None = Field(default=None, description="配置")
    context: dict[str, Any] | None = Field(default=None, description="静态上下文")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")
    assistant_id: str | None = Field(default=None, description="自定义ID")
    if_exists: OnConflictBehavior | None = Field(default=None, description="冲突处理")
    name: str | None = Field(default=None, description="名称")
    description: str | None = Field(default=None, description="描述")


class AssistantUpdateRequest(BaseModel):
    """更新助手请求"""

    graph_id: str | None = Field(default=None, description="图ID")
    config: Config | None = Field(default=None, description="配置")
    context: dict[str, Any] | None = Field(default=None, description="静态上下文")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")
    name: str | None = Field(default=None, description="名称")
    description: str | None = Field(default=None, description="描述")


class AssistantSearchRequest(BaseModel):
    """搜索助手请求"""

    metadata: dict[str, Any] | None = Field(default=None, description="元数据过滤")
    graph_id: str | None = Field(default=None, description="图ID过滤")
    name: str | None = Field(default=None, description="名称模糊匹配")
    limit: int = Field(default=10, description="返回数量限制")
    offset: int = Field(default=0, description="偏移量")
    sort_by: AssistantSortBy | None = Field(default=None, description="排序字段")
    sort_order: SortOrder | None = Field(default=None, description="排序方向")
    select: list[AssistantSelectField] | None = Field(default=None, description="选择返回的字段")


class AssistantCountRequest(BaseModel):
    """统计助手请求"""

    metadata: dict[str, Any] | None = Field(default=None)
    graph_id: str | None = Field(default=None)
    name: str | None = Field(default=None)


class Assistant(BaseModel):
    """助手对象"""

    assistant_id: str = Field(description="助手ID")
    graph_id: str = Field(description="图ID")
    name: str = Field(description="名称")
    description: str | None = Field(default=None, description="描述")
    config: Config | dict[str, Any] = Field(default_factory=dict, description="配置")
    context: dict[str, Any] | None = Field(default=None, description="静态上下文")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")
    version: int = Field(default=1, description="版本号")


class GraphSchema(BaseModel):
    """图Schema"""

    graph_id: str = Field(description="图ID")
    input_schema: dict[str, Any] | None = Field(default=None, description="输入Schema")
    output_schema: dict[str, Any] | None = Field(default=None, description="输出Schema")
    state_schema: dict[str, Any] | None = Field(default=None, description="状态Schema")
    config_schema: dict[str, Any] | None = Field(default=None, description="配置Schema")
    context_schema: dict[str, Any] | None = Field(default=None, description="上下文Schema")


class GraphResponse(BaseModel):
    """图响应"""

    nodes: list[dict[str, Any]] = Field(default_factory=list, description="节点列表")
    edges: list[dict[str, Any]] = Field(default_factory=list, description="边列表")


# ============== Store 相关模型 ==============


class StoreItem(BaseModel):
    """存储项"""

    namespace: list[str] = Field(description="命名空间路径")
    key: str = Field(description="项唯一标识")
    value: dict[str, Any] = Field(description="存储值")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


class StorePutRequest(BaseModel):
    """存储项请求"""

    namespace: list[str] = Field(description="命名空间路径")
    key: str = Field(description="项唯一标识")
    value: dict[str, Any] = Field(description="存储值")


class StoreSearchRequest(BaseModel):
    """搜索存储项请求"""

    namespace: list[str] | None = Field(default=None, description="命名空间前缀")
    filter: dict[str, Any] | None = Field(default=None, description="值过滤")
    limit: int = Field(default=10, description="返回数量限制")
    offset: int = Field(default=0, description="偏移量")


# ============== SSE 事件模型 ==============


class StreamEvent(BaseModel):
    """SSE流事件"""

    event: str = Field(description="事件类型")
    data: dict[str, Any] = Field(description="事件数据")
    id: str | None = Field(default=None, description="事件ID")


class MetadataEvent(BaseModel):
    """运行元数据事件"""

    run_id: str = Field(description="运行ID")


class ValuesEvent(BaseModel):
    """状态值事件"""

    title: str | None = Field(default=None, description="线程标题")
    messages: list[dict[str, Any]] = Field(default_factory=list, description="消息列表")
    artifacts: list[dict[str, Any]] = Field(default_factory=list, description="工件列表")


class EndEvent(BaseModel):
    """流结束事件"""

    usage: dict[str, int] | None = Field(default=None, description="Token使用量")


class ErrorEvent(BaseModel):
    """错误事件"""

    message: str = Field(description="错误信息")
    code: str | None = Field(default=None, description="错误代码")


# ============== 响应模型 ==============


class ThreadCreateResponse(Thread):
    """创建线程响应"""

    pass


class ThreadsListResponse(BaseModel):
    """线程列表响应"""

    threads: list[Thread] = Field(default_factory=list)


class ThreadPruneResponse(BaseModel):
    """清理线程响应"""

    pruned_count: int = Field(description="清理的线程数量")


class RunsListResponse(BaseModel):
    """运行列表响应"""

    runs: list[Run] = Field(default_factory=list)


class AssistantsListResponse(BaseModel):
    """助手列表响应"""

    assistants: list[Assistant] = Field(default_factory=list)


class StoreSearchResponse(BaseModel):
    """搜索存储项响应"""

    items: list[StoreItem] = Field(default_factory=list)


class NamespaceListResponse(BaseModel):
    """命名空间列表响应"""

    namespaces: list[list[str]] = Field(default_factory=list)


# ============== 辅助函数 ==============


def get_current_timestamp() -> str:
    """获取当前ISO 8601时间戳"""
    return datetime.utcnow().isoformat() + "+00:00"


def create_thread_id() -> str:
    """生成线程ID"""
    import uuid

    return str(uuid.uuid4())


def create_run_id() -> str:
    """生成运行ID"""
    import uuid

    return str(uuid.uuid4())
