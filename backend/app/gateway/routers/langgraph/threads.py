"""
Threads API 路由

实现与 LangGraph SDK 完全兼容的线程管理 API
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .client import get_manager
from .schemas import (
    Checkpoint,
    Thread,
    ThreadCountRequest,
    ThreadCreateRequest,
    ThreadHistoryRequest,
    ThreadPruneRequest,
    ThreadPruneResponse,
    ThreadSearchRequest,
    ThreadUpdateRequest,
    ThreadState as ThreadStateResponse,
    UpdateStateResponse,
    UpdateStateRequest,
    get_current_timestamp,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/threads", tags=["langgraph-threads"])


# ============== 线程 CRUD ==============


@router.post("")
async def create_thread(request: ThreadCreateRequest | None = None):
    """
    创建新线程

    完全兼容 LangGraph SDK threads.create()
    """
    manager = get_manager()

    # 处理冲突检查
    if request and request.thread_id:
        existing = manager.threads.get(request.thread_id)
        if existing:
            if request.if_exists == "do_nothing":
                return existing
            elif request.if_exists == "raise":
                raise HTTPException(
                    status_code=409,
                    detail=f"Thread {request.thread_id} already exists",
                )

    # 创建线程
    thread_state = manager.threads.create(
        thread_id=request.thread_id if request else None,
        metadata=request.metadata if request else None,
    )

    return Thread(
        thread_id=thread_state.thread_id,
        created_at=thread_state.created_at,
        updated_at=thread_state.updated_at,
        metadata=thread_state.metadata,
        status=thread_state.status,
        values=thread_state.values,
        interrupts=thread_state.interrupts,
    )


@router.get("/{thread_id}")
async def get_thread(
    thread_id: str,
    include: str | None = Query(default=None, description="逗号分隔的额外字段"),
):
    """
    获取线程

    完全兼容 LangGraph SDK threads.get()
    """
    manager = get_manager()
    thread = manager.threads.get(thread_id)

    if not thread:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    response = Thread(
        thread_id=thread.thread_id,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        metadata=thread.metadata,
        status=thread.status,
        values=thread.values,
        interrupts=thread.interrupts,
    )

    # 处理 include 参数
    # if include and "ttl" in include.split(","):
    #     response.ttl = ...  # 如果实现了 TTL 功能

    return response


@router.patch("/{thread_id}")
async def update_thread(thread_id: str, request: ThreadUpdateRequest):
    """
    更新线程

    完全兼容 LangGraph SDK threads.update()
    """
    manager = get_manager()

    thread = manager.threads.update(
        thread_id=thread_id,
        metadata=request.metadata,
    )

    if not thread:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    return Thread(
        thread_id=thread.thread_id,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        metadata=thread.metadata,
        status=thread.status,
        values=thread.values,
        interrupts=thread.interrupts,
    )


@router.delete("/{thread_id}")
async def delete_thread(thread_id: str):
    """
    删除线程

    完全兼容 LangGraph SDK threads.delete()
    """
    manager = get_manager()

    success = manager.threads.delete(thread_id)
    if not success:
        # LangGraph SDK 在线程不存在时返回成功
        pass

    # 同时清理本地线程数据
    try:
        from deerflow.config.paths import get_paths

        get_paths().delete_thread_dir(thread_id)
    except Exception as e:
        logger.warning("Failed to delete thread data: %s", e)

    return None


# ============== 搜索和统计 ==============


@router.get("")
async def list_threads(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    列出线程

    兼容 LangGraph SDK 的简单列表
    """
    manager = get_manager()
    threads = manager.threads.search(limit=limit, offset=offset)

    return [
        Thread(
            thread_id=t.thread_id,
            created_at=t.created_at,
            updated_at=t.updated_at,
            metadata=t.metadata,
            status=t.status,
            values=t.values,
            interrupts=t.interrupts,
        )
        for t in threads
    ]


@router.post("/search")
async def search_threads(request: ThreadSearchRequest | None = None):
    """
    搜索线程

    完全兼容 LangGraph SDK threads.search()

    注意：SDK 期望直接返回 Thread[] 数组
    """
    manager = get_manager()

    if request is None:
        request = ThreadSearchRequest()

    threads = manager.threads.search(
        metadata=request.metadata,
        status=request.status,
        limit=request.limit,
        offset=request.offset,
    )

    return [
        Thread(
            thread_id=t.thread_id,
            created_at=t.created_at,
            updated_at=t.updated_at,
            metadata=t.metadata,
            status=t.status,
            values=t.values,
            interrupts=t.interrupts,
        )
        for t in threads
    ]


@router.post("/count")
async def count_threads(request: ThreadCountRequest | None = None):
    """
    统计线程数量

    完全兼容 LangGraph SDK threads.count()
    """
    manager = get_manager()

    if request is None:
        request = ThreadCountRequest()

    count = manager.threads.count(
        metadata=request.metadata,
        status=request.status,
    )

    return count


# ============== 线程操作 ==============


@router.post("/{thread_id}/copy")
async def copy_thread(thread_id: str):
    """
    复制线程

    完全兼容 LangGraph SDK threads.copy()
    """
    manager = get_manager()

    original = manager.threads.get(thread_id)
    if not original:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    new_thread = manager.threads.create(
        metadata={
            **original.metadata,
            "copied_from": thread_id,
        },
    )

    manager.threads.update(
        thread_id=new_thread.thread_id,
        values=original.values.copy(),
    )

    return Thread(
        thread_id=new_thread.thread_id,
        created_at=new_thread.created_at,
        updated_at=new_thread.updated_at,
        metadata=new_thread.metadata,
        status=new_thread.status,
        values=new_thread.values,
        interrupts=new_thread.interrupts,
    )


@router.post("/prune", response_model=ThreadPruneResponse)
async def prune_threads(request: ThreadPruneRequest):
    """
    清理线程

    完全兼容 LangGraph SDK threads.prune()
    """
    manager = get_manager()

    pruned_count = 0
    for thread_id in request.thread_ids:
        if manager.threads.delete(thread_id):
            pruned_count += 1

    return ThreadPruneResponse(pruned_count=pruned_count)


# ============== 状态管理 ==============


@router.get("/{thread_id}/state")
async def get_thread_state(
    thread_id: str,
    subgraphs: bool = Query(default=False, description="是否包含子图状态"),
    checkpoint_id: str | None = Query(default=None, description="检查点ID"),
):
    """
    获取线程状态

    完全兼容 LangGraph SDK threads.get_state()
    """
    manager = get_manager()

    thread = manager.threads.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    # 构建检查点信息
    checkpoint = Checkpoint(
        thread_id=thread_id,
        checkpoint_ns="",
        checkpoint_id=checkpoint_id,
    )

    return ThreadStateResponse(
        values=thread.values,
        next=[],  # 暂不支持图节点信息
        checkpoint=checkpoint,
        metadata=thread.metadata,
        created_at=thread.created_at,
    )


@router.post("/{thread_id}/state")
async def update_thread_state(thread_id: str, request: UpdateStateRequest):
    """
    更新线程状态

    完全兼容 LangGraph SDK threads.update_state()

    这个 API 用于：
    1. 重命名线程（前端 useRenameThread）
    2. 更新线程的 values
    3. 从特定节点恢复执行
    """
    manager = get_manager()

    thread = manager.threads.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    # 合并 values
    new_values = thread.values.copy()
    if request.values:
        if isinstance(request.values, dict):
            new_values.update(request.values)
        elif isinstance(request.values, list):
            # 处理列表形式的更新
            for update in request.values:
                if isinstance(update, dict):
                    new_values.update(update)

    # 更新线程
    updated = manager.threads.update(
        thread_id=thread_id,
        values=new_values,
    )

    # 构建响应检查点
    checkpoint = Checkpoint(
        thread_id=thread_id,
        checkpoint_ns="",
        checkpoint_id=request.checkpoint_id,
    )

    return UpdateStateResponse(checkpoint=checkpoint)


@router.post("/{thread_id}/state/checkpoint")
async def get_state_by_checkpoint(thread_id: str, request: dict):
    """
    通过检查点获取状态

    完全兼容 LangGraph SDK threads.get_state(checkpoint=...)
    """
    manager = get_manager()

    thread = manager.threads.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    checkpoint_data = request.get("checkpoint", {})
    subgraphs = request.get("subgraphs", False)

    checkpoint = Checkpoint(
        thread_id=thread_id,
        checkpoint_ns=checkpoint_data.get("checkpoint_ns", ""),
        checkpoint_id=checkpoint_data.get("checkpoint_id"),
    )

    return ThreadStateResponse(
        values=thread.values,
        next=[],
        checkpoint=checkpoint,
        metadata=thread.metadata,
        created_at=thread.created_at,
    )


@router.get("/{thread_id}/state/{checkpoint_id}")
async def get_state_by_checkpoint_id(
    thread_id: str,
    checkpoint_id: str,
    subgraphs: bool = Query(default=False),
):
    """
    通过检查点ID获取状态

    完全兼容 LangGraph SDK threads.get_state(checkpoint_id=...)
    """
    return await get_thread_state(
        thread_id=thread_id,
        subgraphs=subgraphs,
        checkpoint_id=checkpoint_id,
    )


# ============== 历史记录 ==============


@router.post("/{thread_id}/history")
async def get_thread_history(thread_id: str, request: ThreadHistoryRequest | None = None):
    """
    获取线程历史

    完全兼容 LangGraph SDK threads.get_history()

    注意：SDK 期望返回 ThreadState[] 数组
    """
    manager = get_manager()

    thread = manager.threads.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    # 当前实现只返回当前状态作为唯一的"历史"条目
    # 完整实现需要持久化检查点存储

    if request is None:
        request = ThreadHistoryRequest()

    # 构建当前状态的 ThreadState
    checkpoint = Checkpoint(
        thread_id=thread_id,
        checkpoint_ns="",
        checkpoint_id=None,
    )

    current_state = ThreadStateResponse(
        values=thread.values,
        next=[],
        checkpoint=checkpoint,
        metadata=thread.metadata,
        created_at=thread.created_at,
    )

    # 限制返回数量
    limit = request.limit if request else 10
    return [current_state][:limit]


# ============== 线程流 ==============


@router.get("/{thread_id}/stream")
async def join_thread_stream(
    thread_id: str,
    stream_mode: str = Query(default="run_modes"),
    last_event_id: str | None = Query(default=None),
):
    """
    加入线程事件流

    完全兼容 LangGraph SDK threads.join_stream()

    注意：当前实现为占位符，需要实现 SSE 流
    """
    manager = get_manager()

    thread = manager.threads.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    # 当前实现返回空流
    # 完整实现需要支持线程级别的 SSE 事件流

    from fastapi.responses import StreamingResponse
    from .sse import format_sse_event

    async def empty_stream():
        yield format_sse_event("end", None)

    return StreamingResponse(
        empty_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
