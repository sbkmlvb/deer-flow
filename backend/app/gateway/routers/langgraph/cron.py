"""
Cron API 路由

实现与 LangGraph SDK 完全兼容的定时任务调度 API
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .persistence import JSONFileStore
from .schemas import get_current_timestamp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cron", tags=["langgraph-cron"])


@dataclass
class CronConfig:
    """定时任务配置"""

    schedule: str  # cron表达式
    input: dict[str, Any] | None = None
    assistant_id: str = "lead_agent"
    webhook: str | None = None
    multitask_strategy: str | None = None


@dataclass
class CronState:
    """定时任务状态"""

    cron_id: str
    thread_id: str
    schedule: str
    input: dict[str, Any] | None
    assistant_id: str
    webhook: str | None
    multitask_strategy: str | None
    created_at: str
    updated_at: str
    last_run_at: str | None = None
    next_run_at: str | None = None
    status: str = "active"  # active, paused, disabled
    run_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class CronManager:
    """
    定时任务管理器

    管理定时任务的创建、更新、删除和执行
    注意：当前实现只提供API兼容性，实际的调度执行需要外部调度器
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

        # 使用JSON文件持久化
        try:
            from deerflow.config.paths import get_paths

            store_path = (
                Path(get_paths().base_dir) / "cron" / "schedules.json"
            )
        except ImportError:
            store_path = Path(".deer-flow/cron/schedules.json")

        self._store = JSONFileStore(store_path)
        self._data_lock = threading.Lock()
        self._initialized = True

    def create(
        self,
        schedule: str,
        thread_id: str | None = None,
        input: dict[str, Any] | None = None,
        assistant_id: str = "lead_agent",
        webhook: str | None = None,
        multitask_strategy: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CronState:
        """创建定时任务"""
        with self._data_lock:
            cron_id = str(uuid.uuid4())
            now = get_current_timestamp()

            if thread_id is None:
                thread_id = str(uuid.uuid4())

            cron = CronState(
                cron_id=cron_id,
                thread_id=thread_id,
                schedule=schedule,
                input=input,
                assistant_id=assistant_id,
                webhook=webhook,
                multitask_strategy=multitask_strategy,
                created_at=now,
                updated_at=now,
                metadata=metadata or {},
            )

            # 存储到持久化层
            self._store.set(cron_id, self._cron_to_dict(cron))

            return cron

    def get(self, cron_id: str) -> CronState | None:
        """获取定时任务"""
        with self._data_lock:
            data = self._store.get(cron_id)
            if not data:
                return None
            return self._dict_to_cron(data)

    def update(
        self,
        cron_id: str,
        schedule: str | None = None,
        input: dict[str, Any] | None = None,
        webhook: str | None = None,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CronState | None:
        """更新定时任务"""
        with self._data_lock:
            data = self._store.get(cron_id)
            if not data:
                return None

            if schedule is not None:
                data["schedule"] = schedule
            if input is not None:
                data["input"] = input
            if webhook is not None:
                data["webhook"] = webhook
            if status is not None:
                data["status"] = status
            if metadata is not None:
                data["metadata"].update(metadata)

            data["updated_at"] = get_current_timestamp()

            self._store.set(cron_id, data)
            return self._dict_to_cron(data)

    def delete(self, cron_id: str) -> bool:
        """删除定时任务"""
        with self._data_lock:
            return self._store.delete(cron_id)

    def list(
        self,
        thread_id: str | None = None,
        assistant_id: str | None = None,
        status: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[CronState]:
        """列出定时任务"""
        results = []

        with self._data_lock:
            all_data = self._store.values()

            for cron_id, data in all_data.items():
                if not isinstance(data, dict):
                    continue

                # 过滤条件
                if thread_id and data.get("thread_id") != thread_id:
                    continue
                if assistant_id and data.get("assistant_id") != assistant_id:
                    continue
                if status and data.get("status") != status:
                    continue

                results.append(self._dict_to_cron(data))

        # 按创建时间排序（最新的在前）
        results.sort(key=lambda x: x.created_at, reverse=True)

        return results[offset : offset + limit]

    def count(
        self,
        thread_id: str | None = None,
        assistant_id: str | None = None,
        status: str | None = None,
    ) -> int:
        """统计定时任务数量"""
        count = 0

        with self._data_lock:
            all_data = self._store.values()

            for data in all_data.values():
                if not isinstance(data, dict):
                    continue

                if thread_id and data.get("thread_id") != thread_id:
                    continue
                if assistant_id and data.get("assistant_id") != assistant_id:
                    continue
                if status and data.get("status") != status:
                    continue

                count += 1

        return count

    def record_run(self, cron_id: str, success: bool = True) -> None:
        """记录执行"""
        with self._data_lock:
            data = self._store.get(cron_id)
            if not data:
                return

            data["last_run_at"] = get_current_timestamp()
            data["run_count"] = data.get("run_count", 0) + 1
            data["updated_at"] = get_current_timestamp()

            self._store.set(cron_id, data)

    def _cron_to_dict(self, cron: CronState) -> dict[str, Any]:
        """转换CronState为字典"""
        return {
            "cron_id": cron.cron_id,
            "thread_id": cron.thread_id,
            "schedule": cron.schedule,
            "input": cron.input,
            "assistant_id": cron.assistant_id,
            "webhook": cron.webhook,
            "multitask_strategy": cron.multitask_strategy,
            "created_at": cron.created_at,
            "updated_at": cron.updated_at,
            "last_run_at": cron.last_run_at,
            "next_run_at": cron.next_run_at,
            "status": cron.status,
            "run_count": cron.run_count,
            "metadata": cron.metadata,
        }

    def _dict_to_cron(self, data: dict[str, Any]) -> CronState:
        """转换字典为CronState"""
        return CronState(
            cron_id=data["cron_id"],
            thread_id=data["thread_id"],
            schedule=data["schedule"],
            input=data.get("input"),
            assistant_id=data.get("assistant_id", "lead_agent"),
            webhook=data.get("webhook"),
            multitask_strategy=data.get("multitask_strategy"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            last_run_at=data.get("last_run_at"),
            next_run_at=data.get("next_run_at"),
            status=data.get("status", "active"),
            run_count=data.get("run_count", 0),
            metadata=data.get("metadata", {}),
        )


def get_cron_manager() -> CronManager:
    """获取定时任务管理器单例"""
    return CronManager()


# ============== 请求模型 ==============


from pydantic import BaseModel, Field


class CronCreateRequest(BaseModel):
    """创建定时任务请求"""

    schedule: str = Field(description="Cron表达式")
    thread_id: str | None = Field(default=None, description="线程ID")
    input: dict[str, Any] | None = Field(default=None, description="输入数据")
    assistant_id: str = Field(default="lead_agent", description="助手ID")
    webhook: str | None = Field(default=None, description="Webhook URL")
    multitask_strategy: str | None = Field(default=None, description="多任务策略")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")


class CronUpdateRequest(BaseModel):
    """更新定时任务请求"""

    schedule: str | None = Field(default=None, description="Cron表达式")
    input: dict[str, Any] | None = Field(default=None, description="输入数据")
    webhook: str | None = Field(default=None, description="Webhook URL")
    status: str | None = Field(default=None, description="状态")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")


class CronSearchRequest(BaseModel):
    """搜索定时任务请求"""

    thread_id: str | None = Field(default=None, description="线程ID过滤")
    assistant_id: str | None = Field(default=None, description="助手ID过滤")
    status: str | None = Field(default=None, description="状态过滤")
    limit: int = Field(default=10, description="返回数量限制")
    offset: int = Field(default=0, description="偏移量")


# ============== API 端点 ==============


@router.post("")
async def create_cron(request: CronCreateRequest):
    """
    创建定时任务

    完全兼容 LangGraph SDK crons.create()
    """
    manager = get_cron_manager()

    cron = manager.create(
        schedule=request.schedule,
        thread_id=request.thread_id,
        input=request.input,
        assistant_id=request.assistant_id,
        webhook=request.webhook,
        multitask_strategy=request.multitask_strategy,
        metadata=request.metadata,
    )

    return {
        "cron_id": cron.cron_id,
        "thread_id": cron.thread_id,
        "schedule": cron.schedule,
        "assistant_id": cron.assistant_id,
        "created_at": cron.created_at,
        "updated_at": cron.updated_at,
        "status": cron.status,
    }


@router.get("/{cron_id}")
async def get_cron(cron_id: str):
    """
    获取定时任务详情

    完全兼容 LangGraph SDK crons.get()
    """
    manager = get_cron_manager()

    cron = manager.get(cron_id)
    if not cron:
        raise HTTPException(status_code=404, detail=f"Cron {cron_id} not found")

    return {
        "cron_id": cron.cron_id,
        "thread_id": cron.thread_id,
        "schedule": cron.schedule,
        "input": cron.input,
        "assistant_id": cron.assistant_id,
        "webhook": cron.webhook,
        "multitask_strategy": cron.multitask_strategy,
        "created_at": cron.created_at,
        "updated_at": cron.updated_at,
        "last_run_at": cron.last_run_at,
        "next_run_at": cron.next_run_at,
        "status": cron.status,
        "run_count": cron.run_count,
        "metadata": cron.metadata,
    }


@router.patch("/{cron_id}")
async def update_cron(cron_id: str, request: CronUpdateRequest):
    """
    更新定时任务

    完全兼容 LangGraph SDK crons.update()
    """
    manager = get_cron_manager()

    cron = manager.update(
        cron_id=cron_id,
        schedule=request.schedule,
        input=request.input,
        webhook=request.webhook,
        status=request.status,
        metadata=request.metadata,
    )

    if not cron:
        raise HTTPException(status_code=404, detail=f"Cron {cron_id} not found")

    return {
        "cron_id": cron.cron_id,
        "thread_id": cron.thread_id,
        "schedule": cron.schedule,
        "input": cron.input,
        "assistant_id": cron.assistant_id,
        "webhook": cron.webhook,
        "multitask_strategy": cron.multitask_strategy,
        "created_at": cron.created_at,
        "updated_at": cron.updated_at,
        "last_run_at": cron.last_run_at,
        "next_run_at": cron.next_run_at,
        "status": cron.status,
        "run_count": cron.run_count,
        "metadata": cron.metadata,
    }


@router.delete("/{cron_id}")
async def delete_cron(cron_id: str):
    """
    删除定时任务

    完全兼容 LangGraph SDK crons.delete()
    """
    manager = get_cron_manager()

    success = manager.delete(cron_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Cron {cron_id} not found")

    return None


@router.get("")
async def list_crons(
    thread_id: str | None = Query(default=None),
    assistant_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    列出定时任务

    完全兼容 LangGraph SDK crons.list()
    """
    manager = get_cron_manager()

    crons = manager.list(
        thread_id=thread_id,
        assistant_id=assistant_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return [
        {
            "cron_id": c.cron_id,
            "thread_id": c.thread_id,
            "schedule": c.schedule,
            "assistant_id": c.assistant_id,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "status": c.status,
            "run_count": c.run_count,
        }
        for c in crons
    ]


@router.post("/search")
async def search_crons(request: CronSearchRequest | None = None):
    """
    搜索定时任务

    完全兼容 LangGraph SDK crons.search()
    """
    if request is None:
        request = CronSearchRequest()

    manager = get_cron_manager()

    crons = manager.list(
        thread_id=request.thread_id,
        assistant_id=request.assistant_id,
        status=request.status,
        limit=request.limit,
        offset=request.offset,
    )

    return [
        {
            "cron_id": c.cron_id,
            "thread_id": c.thread_id,
            "schedule": c.schedule,
            "input": c.input,
            "assistant_id": c.assistant_id,
            "webhook": c.webhook,
            "multitask_strategy": c.multitask_strategy,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "last_run_at": c.last_run_at,
            "next_run_at": c.next_run_at,
            "status": c.status,
            "run_count": c.run_count,
            "metadata": c.metadata,
        }
        for c in crons
    ]


@router.post("/count")
async def count_crons(request: dict | None = None):
    """
    统计定时任务数量

    完全兼容 LangGraph SDK crons.count()
    """
    if request is None:
        request = {}

    manager = get_cron_manager()

    count = manager.count(
        thread_id=request.get("thread_id"),
        assistant_id=request.get("assistant_id"),
        status=request.get("status"),
    )

    return count
