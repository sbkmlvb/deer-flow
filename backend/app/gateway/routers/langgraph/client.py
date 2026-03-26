"""
LangGraph 兼容层客户端管理

管理 DeerFlowClient 实例和线程状态存储

存储说明：
- 线程元数据（metadata, status）使用 JSON 文件持久化
- 线程 values（messages 等）从 LangGraph checkpointer 读取
- 运行状态使用 JSON 文件持久化
- 使用原子写入确保数据安全
"""

import logging
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from deerflow.client import DeerFlowClient

from .persistence import JSONFileStore

logger = logging.getLogger(__name__)

# 全局锁用于线程安全
_lock = threading.Lock()


@dataclass
class ThreadState:
    """内存中的线程状态"""

    thread_id: str
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "idle"  # idle, busy, interrupted, error
    # values 从 checkpointer 读取，这里只是缓存
    values: dict[str, Any] = field(default_factory=dict)
    interrupts: dict[str, list[dict]] = field(default_factory=dict)


@dataclass
class RunState:
    """内存中的运行状态"""

    run_id: str
    thread_id: str
    assistant_id: str
    created_at: str
    updated_at: str
    status: str = "pending"  # pending, running, success, error, timeout, interrupted
    metadata: dict[str, Any] = field(default_factory=dict)
    multitask_strategy: str | None = None


def _get_checkpointer():
    """获取 checkpointer 实例"""
    from deerflow.agents.checkpointer import get_checkpointer

    return get_checkpointer()


def _serialize_message(msg) -> dict[str, Any]:
    """序列化 LangChain 消息为 dict"""
    result: dict[str, Any] = {
        "type": getattr(msg, "type", "unknown"),
        "content": getattr(msg, "content", ""),
    }
    if hasattr(msg, "id") and msg.id:
        result["id"] = msg.id
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        result["tool_calls"] = [
            {"name": tc.get("name"), "args": tc.get("args"), "id": tc.get("id")}
            for tc in msg.tool_calls
        ]
    if hasattr(msg, "tool_call_id") and msg.tool_call_id:
        result["tool_call_id"] = msg.tool_call_id
    if hasattr(msg, "name") and msg.name:
        result["name"] = msg.name
    if hasattr(msg, "usage_metadata") and msg.usage_metadata:
        result["usage_metadata"] = msg.usage_metadata
    if hasattr(msg, "additional_kwargs") and msg.additional_kwargs:
        result["additional_kwargs"] = msg.additional_kwargs
    return result


def _get_values_from_checkpointer(thread_id: str) -> dict[str, Any]:
    """从 checkpointer 读取线程的最新状态值

    Args:
        thread_id: 线程ID

    Returns:
        包含 messages 等字段的 values 字典
    """
    try:
        checkpointer = _get_checkpointer()
        if checkpointer is None:
            return {"messages": []}

        config = {"configurable": {"thread_id": thread_id}}
        checkpoint_tuple = checkpointer.get_tuple(config)

        if checkpoint_tuple is None:
            return {"messages": []}

        checkpoint = checkpoint_tuple.checkpoint
        if checkpoint is None:
            return {"messages": []}

        # 从 checkpoint 中提取 channel_values
        channel_values = checkpoint.get("channel_values", {})

        # 序列化消息
        values: dict[str, Any] = {}
        for key, value in channel_values.items():
            if key == "messages":
                # 序列化消息列表
                values["messages"] = [
                    _serialize_message(msg) for msg in value
                ]
            else:
                values[key] = value

        return values

    except Exception as e:
        logger.warning("Failed to get values from checkpointer for thread %s: %s", thread_id, e)
        return {"messages": []}


class ThreadStore:
    """
    线程状态存储

    线程元数据（metadata, status）使用 JSON 文件持久化。
    线程 values（messages 等）从 LangGraph checkpointer 实时读取。

    这样确保了：
    1. 元数据（如线程标题、自定义属性）持久化保存
    2. 消息状态由 LangGraph checkpointer 统一管理，避免状态不一致
    """

    def __init__(self, max_size: int = 1000):
        """
        初始化线程存储

        Args:
            max_size: 最大存储线程数量，使用LRU淘汰策略（仅内存）
        """
        # 初始化持久化存储（只存储元数据）
        try:
            from deerflow.config.paths import get_paths

            store_path = Path(get_paths().base_dir) / "langgraph" / "threads.json"
        except ImportError:
            store_path = Path(".deer-flow/langgraph/threads.json")

        self._store = JSONFileStore(store_path)
        self._threads: OrderedDict[str, ThreadState] = OrderedDict()
        self._max_size = max_size
        self._load_from_store()

    def _load_from_store(self):
        """从持久化存储加载元数据"""
        with _lock:
            all_data = self._store.values()
            for thread_id, data in all_data.items():
                if isinstance(data, dict):
                    thread = ThreadState(
                        thread_id=data.get("thread_id", thread_id),
                        created_at=data.get("created_at", ""),
                        updated_at=data.get("updated_at", ""),
                        metadata=data.get("metadata", {}),
                        status=data.get("status", "idle"),
                        # values 不从文件加载，从 checkpointer 读取
                        values={},
                        interrupts=data.get("interrupts", {}),
                    )
                    self._threads[thread_id] = thread

    def _save_thread_metadata(self, thread: ThreadState):
        """保存线程元数据到持久化存储（不包含 values）"""
        data = {
            "thread_id": thread.thread_id,
            "created_at": thread.created_at,
            "updated_at": thread.updated_at,
            "metadata": thread.metadata,
            "status": thread.status,
            # 不保存 values，由 checkpointer 管理
            "interrupts": thread.interrupts,
        }
        self._store.set(thread.thread_id, data)

    def create(
        self,
        thread_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> ThreadState:
        """创建线程"""
        with _lock:
            if thread_id is None:
                thread_id = str(uuid.uuid4())

            now = datetime.utcnow().isoformat() + "+00:00"
            thread = ThreadState(
                thread_id=thread_id,
                created_at=now,
                updated_at=now,
                metadata=metadata or {},
                values={"messages": []},  # 新线程没有消息
                status="idle",
            )
            self._threads[thread_id] = thread
            self._threads.move_to_end(thread_id)
            self._save_thread_metadata(thread)
            self._evict_if_needed()
            return thread

    def get(self, thread_id: str) -> ThreadState | None:
        """获取线程

        会从 checkpointer 读取最新的 values（messages 等）。
        """
        with _lock:
            thread = self._threads.get(thread_id)
            if thread:
                self._threads.move_to_end(thread_id)
                # 从 checkpointer 读取最新的 values
                thread.values = _get_values_from_checkpointer(thread_id)
            return thread

    def update(
        self,
        thread_id: str,
        metadata: dict[str, Any] | None = None,
        status: str | None = None,
        values: dict[str, Any] | None = None,
    ) -> ThreadState | None:
        """更新线程元数据

        Args:
            thread_id: 线程ID
            metadata: 要更新的元数据（会合并）
            status: 要更新的状态
            values: 忽略此参数（values 由 checkpointer 管理）

        Returns:
            更新后的线程状态，如果线程不存在则返回 None
        """
        with _lock:
            thread = self._threads.get(thread_id)
            if not thread:
                return None

            if metadata:
                thread.metadata.update(metadata)
            if status:
                thread.status = status
            # values 参数被忽略，由 checkpointer 管理
            # 但允许更新 title 等非消息字段到 metadata
            if values:
                for key, value in values.items():
                    if key not in ("messages",):  # messages 由 checkpointer 管理
                        thread.metadata[f"_value_{key}"] = value

            thread.updated_at = datetime.utcnow().isoformat() + "+00:00"
            self._threads.move_to_end(thread_id)
            self._save_thread_metadata(thread)

            # 从 checkpointer 读取最新的 values
            thread.values = _get_values_from_checkpointer(thread_id)
            return thread

    def delete(self, thread_id: str) -> bool:
        """删除线程"""
        with _lock:
            if thread_id in self._threads:
                del self._threads[thread_id]
                self._store.delete(thread_id)
                return True
            return False

    def search(
        self,
        metadata: dict[str, Any] | None = None,
        status: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[ThreadState]:
        """搜索线程"""
        with _lock:
            results = []
            for thread in reversed(list(self._threads.values())):
                # 元数据过滤
                if metadata:
                    match = all(
                        thread.metadata.get(k) == v for k, v in metadata.items()
                    )
                    if not match:
                        continue

                # 状态过滤
                if status and thread.status != status:
                    continue

                # 从 checkpointer 读取最新的 values
                thread.values = _get_values_from_checkpointer(thread.thread_id)
                results.append(thread)

            return results[offset : offset + limit]

    def count(
        self,
        metadata: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> int:
        """统计线程数量"""
        with _lock:
            count = 0
            for thread in self._threads.values():
                if metadata:
                    match = all(
                        thread.metadata.get(k) == v for k, v in metadata.items()
                    )
                    if not match:
                        continue
                if status and thread.status != status:
                    continue
                count += 1
            return count

    def _evict_if_needed(self):
        """如果超过最大大小，淘汰最旧的线程（仅从内存）"""
        while len(self._threads) > self._max_size:
            self._threads.popitem(last=False)


class RunStore:
    """
    运行状态存储

    管理运行的生命周期状态，使用JSON文件持久化
    """

    def __init__(self, max_size: int = 5000):
        """初始化运行存储"""
        # 初始化持久化存储
        try:
            from deerflow.config.paths import get_paths

            store_path = Path(get_paths().base_dir) / "langgraph" / "runs.json"
        except ImportError:
            store_path = Path(".deer-flow/langgraph/runs.json")

        self._store = JSONFileStore(store_path)
        self._runs: OrderedDict[str, RunState] = OrderedDict()
        self._thread_runs: dict[str, list[str]] = {}  # thread_id -> [run_ids]
        self._max_size = max_size
        self._load_from_store()

    def _load_from_store(self):
        """从持久化存储加载数据"""
        with _lock:
            all_data = self._store.values()
            for run_id, data in all_data.items():
                if isinstance(data, dict):
                    run = RunState(
                        run_id=data.get("run_id", run_id),
                        thread_id=data.get("thread_id", ""),
                        assistant_id=data.get("assistant_id", "lead_agent"),
                        created_at=data.get("created_at", ""),
                        updated_at=data.get("updated_at", ""),
                        status=data.get("status", "pending"),
                        metadata=data.get("metadata", {}),
                        multitask_strategy=data.get("multitask_strategy"),
                    )
                    self._runs[run_id] = run

                    # 重建线程索引
                    thread_id = run.thread_id
                    if thread_id not in self._thread_runs:
                        self._thread_runs[thread_id] = []
                    self._thread_runs[thread_id].append(run_id)

    def _save_run(self, run: RunState):
        """保存运行到持久化存储"""
        data = {
            "run_id": run.run_id,
            "thread_id": run.thread_id,
            "assistant_id": run.assistant_id,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "status": run.status,
            "metadata": run.metadata,
            "multitask_strategy": run.multitask_strategy,
        }
        self._store.set(run.run_id, data)

    def create(
        self,
        thread_id: str,
        assistant_id: str = "lead_agent",
        metadata: dict[str, Any] | None = None,
        multitask_strategy: str | None = None,
    ) -> RunState:
        """创建运行"""
        with _lock:
            run_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat() + "+00:00"
            run = RunState(
                run_id=run_id,
                thread_id=thread_id,
                assistant_id=assistant_id,
                created_at=now,
                updated_at=now,
                status="pending",
                metadata=metadata or {},
                multitask_strategy=multitask_strategy,
            )
            self._runs[run_id] = run
            self._runs.move_to_end(run_id)

            # 索引线程到运行
            if thread_id not in self._thread_runs:
                self._thread_runs[thread_id] = []
            self._thread_runs[thread_id].append(run_id)

            self._save_run(run)
            self._evict_if_needed()
            return run

    def get(self, run_id: str) -> RunState | None:
        """获取运行"""
        with _lock:
            run = self._runs.get(run_id)
            if run:
                self._runs.move_to_end(run_id)
            return run

    def update(
        self,
        run_id: str,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RunState | None:
        """更新运行状态"""
        with _lock:
            run = self._runs.get(run_id)
            if not run:
                return None

            if status:
                run.status = status
            if metadata:
                run.metadata.update(metadata)

            run.updated_at = datetime.utcnow().isoformat() + "+00:00"
            self._runs.move_to_end(run_id)
            self._save_run(run)
            return run

    def list_by_thread(
        self,
        thread_id: str,
        status: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[RunState]:
        """列出线程的运行"""
        with _lock:
            run_ids = self._thread_runs.get(thread_id, [])
            results = []
            for run_id in reversed(run_ids):
                run = self._runs.get(run_id)
                if not run:
                    continue
                if status and run.status != status:
                    continue
                results.append(run)
            return results[offset : offset + limit]

    def delete(self, run_id: str) -> bool:
        """删除运行"""
        with _lock:
            run = self._runs.get(run_id)
            if not run:
                return False

            # 从线程索引中移除
            thread_id = run.thread_id
            if thread_id in self._thread_runs:
                try:
                    self._thread_runs[thread_id].remove(run_id)
                except ValueError:
                    pass

            del self._runs[run_id]
            self._store.delete(run_id)
            return True

    def _evict_if_needed(self):
        """如果超过最大大小，淘汰最旧的运行（仅从内存）"""
        while len(self._runs) > self._max_size:
            run_id, run = self._runs.popitem(last=False)
            if run.thread_id in self._thread_runs:
                try:
                    self._thread_runs[run.thread_id].remove(run_id)
                except ValueError:
                    pass


class LangGraphClientManager:
    """
    LangGraph 客户端管理器

    管理 DeerFlowClient 实例和状态存储
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._client: DeerFlowClient | None = None
        self._thread_store = ThreadStore()
        self._run_store = RunStore()
        self._initialized = True

    def get_client(self) -> DeerFlowClient:
        """获取或创建 DeerFlowClient 实例"""
        if self._client is None:
            self._client = DeerFlowClient()
        return self._client

    def reset_client(self):
        """重置客户端实例（配置变更后调用）"""
        self._client = None

    @property
    def threads(self) -> ThreadStore:
        """获取线程存储"""
        return self._thread_store

    @property
    def runs(self) -> RunStore:
        """获取运行存储"""
        return self._run_store


# 全局单例
_manager: LangGraphClientManager | None = None


def get_manager() -> LangGraphClientManager:
    """获取全局管理器实例"""
    global _manager
    if _manager is None:
        _manager = LangGraphClientManager()
    return _manager


def get_client() -> DeerFlowClient:
    """获取 DeerFlowClient 实例"""
    return get_manager().get_client()


def reset_client():
    """重置客户端实例"""
    get_manager().reset_client()
