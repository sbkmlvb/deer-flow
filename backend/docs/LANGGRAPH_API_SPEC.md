# LangGraph API 兼容层实现规范

本文档定义了 DeerFlow Gateway 中 LangGraph 兼容层 API 的完整实现规范，确保与 `@langchain/langgraph-sdk` 完全兼容。

**参考源码**: `build/Desktop_Qt_6_8_3-Debug/pyagent/python/local_packages/langgraph/libs/sdk-py/`

---

## 目录

1. [数据类型定义](#1-数据类型定义)
2. [Threads API](#2-threads-api)
3. [Runs API](#3-runs-api)
4. [Assistants API](#4-assistants-api)
5. [Store API](#5-store-api)
6. [Cron API](#6-cron-api)
7. [SSE 流格式](#7-sse-流格式)
8. [实现优先级](#8-实现优先级)

---

## 1. 数据类型定义

### 1.1 基础类型

```python
# ============== 枚举类型 ==============

RunStatus = Literal["pending", "running", "error", "success", "timeout", "interrupted"]
ThreadStatus = Literal["idle", "busy", "interrupted", "error"]
StreamMode = Literal["values", "messages", "updates", "events", "tasks", "checkpoints", "debug", "custom", "messages-tuple"]
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

# 排序字段
AssistantSortBy = Literal["assistant_id", "graph_id", "name", "created_at", "updated_at"]
ThreadSortBy = Literal["thread_id", "status", "created_at", "updated_at", "state_updated_at"]
CronSortBy = Literal["cron_id", "assistant_id", "thread_id", "created_at", "updated_at", "next_run_date", "end_time"]

# ============== 通用类型 ==============

Json = dict[str, Any] | None
All = Literal["*"]
```

### 1.2 Config

```python
class Config(TypedDict, total=False):
    """运行配置"""
    tags: list[str]
    """标签列表，用于过滤调用"""
    recursion_limit: int
    """最大递归次数，默认25"""
    configurable: dict[str, Any]
    """运行时可配置参数"""
```

### 1.3 Checkpoint

```python
class Checkpoint(TypedDict):
    """检查点"""
    thread_id: str
    """线程ID"""
    checkpoint_ns: str
    """检查点命名空间，用于子图状态管理"""
    checkpoint_id: str | None
    """检查点ID"""
    checkpoint_map: dict[str, Any] | None
    """检查点数据映射"""
```

### 1.4 Thread

```python
class Thread(TypedDict):
    """线程对象"""
    thread_id: str
    """线程唯一标识"""
    created_at: str  # ISO 8601 datetime
    """创建时间"""
    updated_at: str  # ISO 8601 datetime
    """更新时间"""
    metadata: Json
    """元数据"""
    status: ThreadStatus
    """状态: idle, busy, interrupted, error"""
    values: Json
    """当前状态值"""
    interrupts: dict[str, list[Interrupt]]
    """中断映射: task_id -> interrupts"""
    extracted: NotRequired[dict[str, Any]]
    """提取的值（仅在使用extract参数时返回）"""
```

### 1.5 Interrupt

```python
class Interrupt(TypedDict):
    """中断对象"""
    value: Any
    """中断关联的值"""
    id: str
    """中断ID，可用于恢复"""
```

### 1.6 ThreadState

```python
class ThreadState(TypedDict):
    """线程状态"""
    values: list[dict] | dict[str, Any]
    """状态值"""
    next: list[str]
    """下一步要执行的节点，为空表示完成"""
    checkpoint: Checkpoint
    """当前检查点"""
    metadata: Json
    """状态元数据"""
    created_at: str | None
    """创建时间戳"""
    parent_config: Checkpoint | None
    """父检查点配置"""
    tasks: list[ThreadTask]
    """待执行任务"""
    interrupts: list[Interrupt]
    """抛出的中断"""
```

### 1.7 ThreadTask

```python
class ThreadTask(TypedDict):
    """线程任务"""
    id: str
    """任务ID"""
    name: str
    """节点名称"""
    error: str | None
    """错误信息"""
    interrupts: list[Interrupt]
    """中断列表"""
    checkpoint: Checkpoint | None
    """检查点"""
    state: ThreadState | None
    """子图状态"""
    result: dict[str, Any] | None
    """执行结果"""
```

### 1.8 ThreadUpdateStateResponse

```python
class ThreadUpdateStateResponse(TypedDict):
    """更新线程状态的响应"""
    checkpoint: Checkpoint
    """更新后的检查点"""
```

### 1.9 Run

```python
class Run(TypedDict):
    """运行对象"""
    run_id: str
    """运行ID"""
    thread_id: str
    """线程ID"""
    assistant_id: str
    """助手ID"""
    created_at: str  # ISO 8601 datetime
    """创建时间"""
    updated_at: str  # ISO 8601 datetime
    """更新时间"""
    status: RunStatus
    """状态: pending, running, error, success, timeout, interrupted"""
    metadata: Json
    """元数据"""
    multitask_strategy: MultitaskStrategy | None
    """多任务策略"""
```

### 1.10 Assistant

```python
class Assistant(TypedDict):
    """助手对象"""
    assistant_id: str
    """助手ID"""
    graph_id: str
    """图ID"""
    config: Config
    """配置"""
    context: dict[str, Any]
    """静态上下文"""
    created_at: str  # ISO 8601 datetime
    """创建时间"""
    updated_at: str  # ISO 8601 datetime
    """更新时间"""
    metadata: Json
    """元数据"""
    version: int
    """版本号"""
    name: str
    """名称"""
    description: str | None
    """描述"""
```

### 1.11 GraphSchema

```python
class GraphSchema(TypedDict):
    """图Schema"""
    graph_id: str
    """图ID"""
    input_schema: dict | None
    """输入Schema"""
    output_schema: dict | None
    """输出Schema"""
    state_schema: dict | None
    """状态Schema"""
    config_schema: dict | None
    """配置Schema"""
    context_schema: dict | None
    """上下文Schema"""
```

### 1.12 Command

```python
class Command(TypedDict, total=False):
    """控制命令"""
    goto: str | Send | list[str | Send]
    """跳转目标"""
    update: dict[str, Any] | list[tuple[str, Any]]
    """状态更新"""
    resume: Any
    """恢复值"""
```

### 1.13 Send

```python
class Send(TypedDict):
    """发送消息"""
    node: str
    """目标节点"""
    input: dict[str, Any] | None
    """输入数据"""
```

### 1.14 StreamPart (SSE事件)

```python
class StreamPart(NamedTuple):
    """SSE流事件"""
    event: str
    """事件类型"""
    data: dict
    """事件数据"""
    id: str | None = None
    """事件ID"""
```

---

## 2. Threads API

### 2.1 创建线程

**端点**: `POST /threads`

**请求体**:
```python
class ThreadCreateRequest(TypedDict, total=False):
    thread_id: str | None
    """可选的线程ID，不提供则自动生成UUID"""
    metadata: Json
    """元数据"""
    if_exists: OnConflictBehavior | None
    """冲突处理: raise(默认), do_nothing"""
    supersteps: list[Superstep] | None
    """初始超步骤，用于复制线程"""
    graph_id: str | None
    """关联的图ID"""
    ttl: int | TTLConfig | None
    """TTL配置（分钟）"""

class Superstep(TypedDict):
    updates: list[SuperstepUpdate]

class SuperstepUpdate(TypedDict):
    values: dict[str, Any]
    command: Command | None
    as_node: str

class TTLConfig(TypedDict, total=False):
    ttl: int
    """TTL分钟数"""
    strategy: Literal["delete"]
    """策略，默认delete"""
```

**响应**: `Thread`

**示例请求**:
```json
{
  "thread_id": "my-thread-id",
  "metadata": {"user_id": "123"},
  "if_exists": "do_nothing"
}
```

**示例响应**:
```json
{
  "thread_id": "my-thread-id",
  "created_at": "2024-07-18T18:35:15.540834+00:00",
  "updated_at": "2024-07-18T18:35:15.540834+00:00",
  "metadata": {"user_id": "123"},
  "status": "idle",
  "values": {},
  "interrupts": {}
}
```

---

### 2.2 获取线程

**端点**: `GET /threads/{thread_id}`

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `include` | str | 逗号分隔的额外字段，支持 `"ttl"` |

**响应**: `Thread`

**示例请求**:
```
GET /threads/my-thread-id?include=ttl
```

**示例响应**:
```json
{
  "thread_id": "my-thread-id",
  "created_at": "2024-07-18T18:35:15.540834+00:00",
  "updated_at": "2024-07-18T18:35:15.540834+00:00",
  "metadata": {},
  "status": "idle",
  "values": {"messages": []},
  "interrupts": {}
}
```

---

### 2.3 更新线程

**端点**: `PATCH /threads/{thread_id}`

**请求体**:
```python
class ThreadUpdateRequest(TypedDict, total=False):
    metadata: Mapping[str, Any]
    """要合并的元数据"""
    ttl: int | TTLConfig | None
    """TTL配置"""
```

**响应**: `Thread`

---

### 2.4 删除线程

**端点**: `DELETE /threads/{thread_id}`

**响应**: `None` (HTTP 204 或 200 with empty body)

---

### 2.5 搜索线程

**端点**: `POST /threads/search`

**请求体**:
```python
class ThreadSearchRequest(TypedDict, total=False):
    metadata: Json
    """元数据过滤"""
    values: Json
    """状态值过滤"""
    ids: list[str] | None
    """线程ID列表过滤"""
    status: ThreadStatus | None
    """状态过滤: idle, busy, interrupted, error"""
    limit: int
    """返回数量限制，默认10"""
    offset: int
    """偏移量，默认0"""
    sort_by: ThreadSortBy | None
    """排序字段"""
    sort_order: SortOrder | None
    """排序方向: asc, desc"""
    select: list[Literal[
        "thread_id", "created_at", "updated_at", "metadata",
        "config", "context", "status", "values", "interrupts"
    ]] | None
    """选择返回的字段"""
    extract: dict[str, str] | None
    """提取字段映射，如 {"last_msg": "values.messages[-1]"}"""
```

**响应**: `list[Thread]`

**示例请求**:
```json
{
  "limit": 15,
  "offset": 0,
  "sort_by": "updated_at",
  "sort_order": "desc",
  "status": "idle"
}
```

**示例响应**:
```json
[
  {
    "thread_id": "thread-1",
    "created_at": "2024-07-18T18:35:15.540834+00:00",
    "updated_at": "2024-07-18T18:40:00.000000+00:00",
    "metadata": {},
    "status": "idle",
    "values": {"messages": [...]},
    "interrupts": {}
  }
]
```

---

### 2.6 统计线程数

**端点**: `POST /threads/count`

**请求体**:
```python
class ThreadCountRequest(TypedDict, total=False):
    metadata: Json
    values: Json
    status: ThreadStatus | None
```

**响应**: `int`

---

### 2.7 复制线程

**端点**: `POST /threads/{thread_id}/copy`

**响应**: `Thread` (新线程)

---

### 2.8 清理线程

**端点**: `POST /threads/prune`

**请求体**:
```python
class ThreadPruneRequest(TypedDict):
    thread_ids: list[str]
    """要清理的线程ID列表"""
    strategy: PruneStrategy
    """策略: delete(默认), keep_latest"""
```

**响应**:
```python
class ThreadPruneResponse(TypedDict):
    pruned_count: int
    """清理的线程数量"""
```

---

### 2.9 获取线程状态

**端点**: `GET /threads/{thread_id}/state`

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `subgraphs` | bool | 是否包含子图状态 |

**响应**: `ThreadState`

---

### 2.10 获取指定检查点状态

**端点**: `GET /threads/{thread_id}/state/{checkpoint_id}`

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `subgraphs` | bool | 是否包含子图状态 |

**响应**: `ThreadState`

---

### 2.11 通过检查点获取状态

**端点**: `POST /threads/{thread_id}/state/checkpoint`

**请求体**:
```python
class CheckpointStateRequest(TypedDict):
    checkpoint: Checkpoint
    subgraphs: bool
```

**响应**: `ThreadState`

---

### 2.12 更新线程状态

**端点**: `POST /threads/{thread_id}/state`

**请求体**:
```python
class UpdateStateRequest(TypedDict, total=False):
    values: dict[str, Any] | list[dict] | None
    """要更新的值"""
    as_node: str | None
    """模拟的节点名称"""
    checkpoint: Checkpoint | None
    """检查点"""
    checkpoint_id: str | None
    """检查点ID（已废弃，使用checkpoint）"""
```

**响应**: `ThreadUpdateStateResponse`

**示例请求**:
```json
{
  "values": {"title": "New Thread Title"},
  "as_node": "agent"
}
```

**示例响应**:
```json
{
  "checkpoint": {
    "thread_id": "thread-1",
    "checkpoint_ns": "",
    "checkpoint_id": "new-checkpoint-id",
    "checkpoint_map": {}
  }
}
```

---

### 2.13 获取线程历史

**端点**: `POST /threads/{thread_id}/history`

**请求体**:
```python
class ThreadHistoryRequest(TypedDict, total=False):
    limit: int
    """最大返回数量，默认10"""
    before: str | Checkpoint | None
    """返回此检查点之前的状态"""
    metadata: Mapping[str, Any] | None
    """元数据过滤"""
    checkpoint: Checkpoint | None
    """子图检查点"""
```

**响应**: `list[ThreadState]`

---

### 2.14 加入线程流

**端点**: `GET /threads/{thread_id}/stream`

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `stream_mode` | ThreadStreamMode | 流模式: run_modes, lifecycle, state_update |
| `last_event_id` | str | 最后事件ID，用于恢复 |

**响应**: SSE 流 `Iterator[StreamPart]`

---

## 3. Runs API

### 3.1 创建流式运行

**端点**: `POST /threads/{thread_id}/runs/stream`

**无状态端点**: `POST /runs/stream` (不需要thread_id)

**请求体**:
```python
class RunStreamRequest(TypedDict, total=False):
    assistant_id: str
    """助手ID或图名称，必填"""
    input: dict[str, Any] | None
    """输入数据"""
    command: Command | None
    """控制命令"""
    stream_mode: StreamMode | list[StreamMode]
    """流模式，默认 'values'"""
    stream_subgraphs: bool
    """是否流式输出子图"""
    stream_resumable: bool
    """是否可恢复"""
    metadata: Mapping[str, Any] | None
    """运行元数据"""
    config: Config | None
    """配置"""
    context: dict[str, Any] | None
    """静态上下文"""
    checkpoint: Checkpoint | None
    """恢复的检查点"""
    checkpoint_id: str | None
    """恢复的检查点ID（已废弃）"""
    checkpoint_during: bool | None
    """是否运行时检查点（已废弃，使用durability）"""
    interrupt_before: All | list[str] | None
    """执行前中断的节点"""
    interrupt_after: All | list[str] | None
    """执行后中断的节点"""
    feedback_keys: list[str] | None
    """反馈键"""
    on_disconnect: DisconnectMode | None
    """断开行为: cancel, continue"""
    webhook: str | None
    """完成回调URL"""
    multitask_strategy: MultitaskStrategy | None
    """多任务策略: reject, interrupt, rollback, enqueue"""
    if_not_exists: IfNotExists | None
    """线程不存在时的行为: reject, create"""
    on_completion: OnCompletionBehavior | None
    """完成后的行为（无状态运行）: delete, keep"""
    after_seconds: int | None
    """延迟执行秒数"""
    durability: Durability | None
    """持久化模式: sync, async, exit"""
```

**响应**: SSE 流 `Iterator[StreamPart]`

**示例请求**:
```json
{
  "assistant_id": "lead_agent",
  "input": {
    "messages": [
      {"type": "human", "content": "Hello!"}
    ]
  },
  "stream_mode": ["values", "messages-tuple"],
  "config": {
    "configurable": {
      "model_name": "gpt-4"
    }
  }
}
```

**SSE 事件格式**:
```
event: metadata
data: {"run_id": "run-123"}

event: values
data: {"messages": [...]}

event: end
data: null
```

---

### 3.2 创建后台运行

**端点**: `POST /threads/{thread_id}/runs`

**无状态端点**: `POST /runs`

**请求体**: 同 `RunStreamRequest`

**响应**: `Run`

**示例响应**:
```json
{
  "run_id": "run-123",
  "thread_id": "thread-1",
  "assistant_id": "lead_agent",
  "created_at": "2024-07-25T15:35:42.598503+00:00",
  "updated_at": "2024-07-25T15:35:42.598503+00:00",
  "status": "pending",
  "metadata": {},
  "multitask_strategy": null
}
```

---

### 3.3 创建运行并等待

**端点**: `POST /threads/{thread_id}/runs/wait`

**无状态端点**: `POST /runs/wait`

**请求体**:
```python
class RunWaitRequest(TypedDict, total=False):
    # 同 RunStreamRequest，额外增加:
    raise_error: bool
    """是否在错误时抛出异常，默认True"""
```

**响应**: `dict[str, Any]` (最终状态值)

**示例响应**:
```json
{
  "messages": [
    {"type": "human", "content": "Hello!"},
    {"type": "ai", "content": "Hi there!"}
  ]
}
```

---

### 3.4 批量创建运行

**端点**: `POST /runs/batch`

**请求体**: `list[RunCreate]`

**响应**: `list[Run]`

---

### 3.5 列出运行

**端点**: `GET /threads/{thread_id}/runs`

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `limit` | int | 默认10 |
| `offset` | int | 默认0 |
| `status` | RunStatus | 状态过滤 |
| `select` | list[str] | 选择字段 |

**响应**: `list[Run]`

---

### 3.6 获取运行

**端点**: `GET /threads/{thread_id}/runs/{run_id}`

**响应**: `Run`

---

### 3.7 取消运行

**端点**: `POST /threads/{thread_id}/runs/{run_id}/cancel`

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `wait` | int | 0或1，是否等待完成 |
| `action` | CancelAction | interrupt(默认), rollback |

**响应**: `None`

---

### 3.8 批量取消运行

**端点**: `POST /runs/cancel`

**请求体**:
```python
class BulkCancelRequest(TypedDict, total=False):
    thread_id: str | None
    run_ids: list[str] | None
    status: BulkCancelRunsStatus | None
    """pending, running, all"""
    action: CancelAction
```

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `action` | CancelAction | interrupt(默认), rollback |

**响应**: `None`

---

### 3.9 加入运行

**端点**: `GET /threads/{thread_id}/runs/{run_id}/join`

**响应**: `dict` (最终线程状态)

---

### 3.10 加入运行流

**端点**: `GET /threads/{thread_id}/runs/{run_id}/stream`

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `stream_mode` | StreamMode | list[StreamMode] |
| `cancel_on_disconnect` | bool | 断开时取消 |
| `last_event_id` | str | 恢复事件ID |

**响应**: SSE 流 `Iterator[StreamPart]`

---

### 3.11 删除运行

**端点**: `DELETE /threads/{thread_id}/runs/{run_id}`

**响应**: `None`

---

## 4. Assistants API

### 4.1 获取助手

**端点**: `GET /assistants/{assistant_id}`

**响应**: `Assistant`

**示例响应**:
```json
{
  "assistant_id": "lead_agent",
  "graph_id": "lead_agent",
  "name": "Lead Agent",
  "description": "DeerFlow主代理",
  "config": {},
  "context": {},
  "created_at": "2024-06-25T17:10:33.109781+00:00",
  "updated_at": "2024-06-25T17:10:33.109781+00:00",
  "metadata": {"created_by": "system"},
  "version": 1
}
```

---

### 4.2 获取助手图

**端点**: `GET /assistants/{assistant_id}/graph`

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `xray` | int | bool | 包含子图深度 |

**响应**:
```python
class GraphResponse(TypedDict):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
```

---

### 4.3 获取助手Schema

**端点**: `GET /assistants/{assistant_id}/schemas`

**响应**: `GraphSchema`

---

### 4.4 获取子图

**端点**: `GET /assistants/{assistant_id}/subgraphs`

**端点**: `GET /assistants/{assistant_id}/subgraphs/{namespace}`

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `recurse` | bool | 递归获取 |

**响应**: `dict[str, GraphSchema]` (Subgraphs)

---

### 4.5 创建助手

**端点**: `POST /assistants`

**请求体**:
```python
class AssistantCreateRequest(TypedDict, total=False):
    graph_id: str | None
    """图ID"""
    config: Config | None
    """配置"""
    context: dict[str, Any] | None
    """静态上下文"""
    metadata: Json
    """元数据"""
    assistant_id: str | None
    """自定义ID"""
    if_exists: OnConflictBehavior | None
    """冲突处理"""
    name: str | None
    """名称"""
    description: str | None
    """描述"""
```

**响应**: `Assistant`

---

### 4.6 更新助手

**端点**: `PATCH /assistants/{assistant_id}`

**请求体**:
```python
class AssistantUpdateRequest(TypedDict, total=False):
    graph_id: str | None
    config: Config | None
    context: dict[str, Any] | None
    metadata: Json
    name: str | None
    description: str | None
```

**响应**: `Assistant`

---

### 4.7 删除助手

**端点**: `DELETE /assistants/{assistant_id}`

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `delete_threads` | bool | 是否同时删除关联线程 |

**响应**: `None`

---

### 4.8 搜索助手

**端点**: `POST /assistants/search`

**请求体**:
```python
class AssistantSearchRequest(TypedDict, total=False):
    metadata: Json
    graph_id: str | None
    name: str | None
    """名称模糊匹配"""
    limit: int
    """默认10"""
    offset: int
    """默认0"""
    sort_by: AssistantSortBy | None
    sort_order: SortOrder | None
    select: list[str] | None
    response_format: Literal["array", "object"]
    """array(默认) 或 object(带分页)"""
```

**响应**:
- `response_format="array"`: `list[Assistant]`
- `response_format="object"`:
```python
class AssistantsSearchResponse(TypedDict):
    assistants: list[Assistant]
    next: str | None  # 分页游标
```

---

### 4.9 统计助手数

**端点**: `POST /assistants/count`

**请求体**:
```python
class AssistantCountRequest(TypedDict, total=False):
    metadata: Json
    graph_id: str | None
    name: str | None
```

**响应**: `int`

---

### 4.10 获取助手版本

**端点**: `POST /assistants/{assistant_id}/versions`

**请求体**:
```python
class AssistantVersionsRequest(TypedDict, total=False):
    metadata: Json
    limit: int
    offset: int
```

**响应**: `list[AssistantVersion]`

---

### 4.11 设置最新版本

**端点**: `POST /assistants/{assistant_id}/latest`

**请求体**:
```python
class SetLatestRequest(TypedDict):
    version: int
```

**响应**: `Assistant`

---

## 5. Store API

### 5.1 存储项

```python
class Item(TypedDict):
    namespace: list[str]
    """命名空间路径"""
    key: str
    """项唯一标识"""
    value: dict[str, Any]
    """存储值"""
    created_at: str
    updated_at: str

class SearchItem(Item, total=False):
    score: float | None
    """搜索相关性分数"""
```

### 5.2 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/store/items` | PUT | 存储项 |
| `/store/items/{namespace}/{key}` | GET | 获取项 |
| `/store/items/{namespace}/{key}` | DELETE | 删除项 |
| `/store/items/search` | POST | 搜索项 |
| `/store/namespaces` | GET | 列出命名空间 |

---

## 6. Cron API

### 6.1 Cron对象

```python
class Cron(TypedDict):
    cron_id: str
    assistant_id: str
    thread_id: str | None
    on_run_completed: OnCompletionBehavior | None
    end_time: str | None
    schedule: str
    timezone: str | None
    created_at: str
    updated_at: str
    payload: dict
    user_id: str | None
    next_run_date: str | None
    metadata: dict
    enabled: bool
```

### 6.2 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/threads/{thread_id}/runs/crons` | POST | 创建定时任务 |
| `/threads/{thread_id}/runs/crons` | GET | 列出定时任务 |
| `/threads/{thread_id}/runs/crons/{cron_id}` | GET | 获取定时任务 |
| `/threads/{thread_id}/runs/crons/{cron_id}` | PATCH | 更新定时任务 |
| `/threads/{thread_id}/runs/crons/{cron_id}` | DELETE | 删除定时任务 |
| `/runs/crons/search` | POST | 搜索定时任务 |
| `/runs/crons/count` | POST | 统计定时任务 |

---

## 7. SSE 流格式

### 7.1 事件类型

| 事件 | 说明 | 数据格式 |
|------|------|----------|
| `metadata` | 运行元数据 | `{"run_id": "..."}` |
| `values` | 完整状态值 | `ThreadState.values` |
| `messages/partial` | 部分消息 | `[partial_message_chunks]` |
| `messages/complete` | 完整消息 | `[complete_messages]` |
| `messages/metadata` | 消息元数据 | `{"langgraph_step": 1, ...}` |
| `messages` | 消息元组 | `[message, metadata]` |
| `messages-tuple` | 消息元组（别名） | `[message, metadata]` |
| `updates` | 节点更新 | `{node_name: output}` |
| `custom` | 自定义事件 | 任意 |
| `checkpoints` | 检查点 | `CheckpointPayload` |
| `tasks` | 任务事件 | `TaskPayload | TaskResultPayload` |
| `debug` | 调试事件 | `DebugPayload` |
| `end` | 流结束 | `null` |
| `error` | 错误 | `{"message": "..."}` |

### 7.2 SSE 格式规范

```
event: {event_type}
data: {json_data}

```

**示例**:
```
event: metadata
data: {"run_id": "run-123-abc"}

event: values
data: {"messages": [{"type": "human", "content": "Hello"}]}

event: end
data: null

```

### 7.3 V2 流格式

```python
class StreamPartV2(TypedDict):
    type: Literal["values", "updates", "messages/partial", "messages/complete",
                  "messages/metadata", "messages", "custom", "checkpoints",
                  "tasks", "debug", "metadata"]
    ns: list[str]  # 命名空间路径
    data: Any
```

---

## 8. 实现优先级

### P0 - 核心功能（必须实现）

| API | 当前状态 | 说明 |
|-----|----------|------|
| `POST /threads` | ⚠️ 部分 | 需完整参数支持 |
| `GET /threads/{thread_id}` | ⚠️ 部分 | 需返回完整Thread对象 |
| `DELETE /threads/{thread_id}` | ✅ | - |
| `POST /threads/search` | ⚠️ 部分 | 需返回真实数据 |
| `POST /threads/{thread_id}/state` | ❌ | **前端重命名功能依赖此API** |
| `POST /threads/{thread_id}/history` | ⚠️ 部分 | 需返回历史状态 |
| `POST /threads/{thread_id}/runs/stream` | ⚠️ 部分 | 需完整参数支持 |
| `POST /threads/{thread_id}/runs/wait` | ⚠️ 部分 | 需完整参数支持 |
| `GET /assistants` | ⚠️ 部分 | 需返回完整Assistant对象 |
| `GET /assistants/{id}` | ⚠️ 部分 | 需返回完整Assistant对象 |

### P1 - 重要功能

| API | 当前状态 | 说明 |
|-----|----------|------|
| `PATCH /threads/{thread_id}` | ❌ | 更新线程元数据 |
| `POST /threads/count` | ❌ | 统计线程 |
| `GET /threads/{thread_id}/state` | ❌ | 获取状态 |
| `GET /threads/{thread_id}/runs` | ❌ | 列出运行 |
| `GET /threads/{thread_id}/runs/{run_id}` | ❌ | 获取运行 |
| `POST /threads/{thread_id}/runs/{run_id}/cancel` | ❌ | 取消运行 |
| `GET /assistants/{id}/schemas` | ❌ | 获取Schema |

### P2 - 增强功能

| API | 当前状态 | 说明 |
|-----|----------|------|
| `POST /threads/{thread_id}/copy` | ❌ | 复制线程 |
| `POST /threads/prune` | ❌ | 清理线程 |
| `GET /threads/{thread_id}/stream` | ❌ | 线程流 |
| `POST /assistants` | ❌ | 创建助手 |
| `PATCH /assistants/{id}` | ❌ | 更新助手 |
| `DELETE /assistants/{id}` | ❌ | 删除助手 |
| Store API | ❌ | 跨线程存储 |
| Cron API | ❌ | 定时任务 |

---

## 9. 实现检查清单

### 9.1 Threads API

- [ ] `POST /threads` - 完整参数支持
  - [ ] `thread_id` 可选
  - [ ] `metadata` 支持
  - [ ] `if_exists` 冲突处理
  - [ ] `supersteps` 初始化
  - [ ] `graph_id` 关联
  - [ ] `ttl` 过期配置

- [ ] `GET /threads/{thread_id}` - 返回完整Thread
  - [ ] `include` 查询参数
  - [ ] 完整字段: thread_id, created_at, updated_at, metadata, status, values, interrupts

- [ ] `PATCH /threads/{thread_id}` - 更新线程
  - [ ] `metadata` 合并
  - [ ] `ttl` 更新

- [ ] `DELETE /threads/{thread_id}` - 删除线程
  - [ ] 返回正确格式

- [ ] `POST /threads/search` - 搜索线程
  - [ ] `metadata` 过滤
  - [ ] `values` 过滤
  - [ ] `ids` 过滤
  - [ ] `status` 过滤
  - [ ] `limit`/`offset` 分页
  - [ ] `sort_by`/`sort_order` 排序
  - [ ] `select` 字段选择
  - [ ] `extract` 字段提取

- [ ] `POST /threads/count` - 统计线程

- [ ] `POST /threads/{thread_id}/copy` - 复制线程

- [ ] `POST /threads/prune` - 清理线程

- [ ] `GET /threads/{thread_id}/state` - 获取状态
  - [ ] `subgraphs` 参数

- [ ] `POST /threads/{thread_id}/state` - 更新状态
  - [ ] `values` 更新
  - [ ] `as_node` 模拟节点
  - [ ] `checkpoint` 指定检查点
  - [ ] 返回 `ThreadUpdateStateResponse`

- [ ] `POST /threads/{thread_id}/history` - 获取历史
  - [ ] `limit` 限制
  - [ ] `before` 分页
  - [ ] `metadata` 过滤
  - [ ] 返回 `list[ThreadState]`

- [ ] `GET /threads/{thread_id}/stream` - 线程流

### 9.2 Runs API

- [ ] `POST /threads/{thread_id}/runs/stream` - 流式运行
  - [ ] 所有请求参数
  - [ ] SSE 事件格式
  - [ ] 所有 stream_mode 支持

- [ ] `POST /threads/{thread_id}/runs` - 创建运行
  - [ ] 返回完整 `Run` 对象

- [ ] `POST /threads/{thread_id}/runs/wait` - 等待运行
  - [ ] `raise_error` 参数
  - [ ] 返回最终状态

- [ ] `GET /threads/{thread_id}/runs` - 列出运行

- [ ] `GET /threads/{thread_id}/runs/{run_id}` - 获取运行

- [ ] `POST /threads/{thread_id}/runs/{run_id}/cancel` - 取消运行
  - [ ] `wait` 参数
  - [ ] `action` 参数

- [ ] `DELETE /threads/{thread_id}/runs/{run_id}` - 删除运行

- [ ] `GET /threads/{thread_id}/runs/{run_id}/join` - 加入运行

- [ ] `GET /threads/{thread_id}/runs/{run_id}/stream` - 加入运行流

- [ ] `POST /runs/stream` - 无状态流式运行

- [ ] `POST /runs` - 无状态运行

- [ ] `POST /runs/wait` - 无状态等待运行

- [ ] `POST /runs/batch` - 批量创建

- [ ] `POST /runs/cancel` - 批量取消

### 9.3 Assistants API

- [ ] `GET /assistants/{assistant_id}` - 完整Assistant对象
  - [ ] 所有必需字段

- [ ] `GET /assistants/{assistant_id}/graph` - 获取图

- [ ] `GET /assistants/{assistant_id}/schemas` - 获取Schema

- [ ] `GET /assistants/{assistant_id}/subgraphs` - 获取子图

- [ ] `POST /assistants/search` - 搜索助手
  - [ ] 分页支持
  - [ ] 过滤支持

- [ ] `POST /assistants/count` - 统计助手

---

## 10. 参考链接

- LangGraph SDK Python: `build/Desktop_Qt_6_8_3-Debug/pyagent/python/local_packages/langgraph/libs/sdk-py/`
- 兼容层实现: `deer-flow/backend/app/gateway/routers/langgraph.py`
- 前端API调用: `deer-flow/frontend/src/core/threads/hooks.ts`
