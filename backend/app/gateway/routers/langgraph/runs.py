"""
Runs API 路由

实现与 LangGraph SDK 完全兼容的运行管理 API
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .client import get_manager
from .schemas import (
    Run,
    RunCancelRequest,
    RunCreateRequest,
    RunListRequest,
    RunStreamRequest,
    RunWaitRequest,
    get_current_timestamp,
)
from .sse import (
    SSEEventBuilder,
    deerflow_stream_to_langgraph_sse,
    extract_user_message,
    get_sse_headers,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["langgraph-runs"])


# ============== 流式运行 ==============


@router.post("/threads/{thread_id}/runs/stream")
async def stream_run(thread_id: str, request: RunStreamRequest):
    """
    创建流式运行

    完全兼容 LangGraph SDK runs.stream()
    """
    manager = get_manager()

    # 确保线程存在
    thread = manager.threads.get(thread_id)
    if not thread:
        # 检查 if_not_exists 参数
        if request.if_not_exists == "reject":
            raise HTTPException(
                status_code=404,
                detail=f"Thread {thread_id} not found",
            )
        # 创建线程
        thread = manager.threads.create(thread_id=thread_id)

    # 创建运行记录
    run = manager.runs.create(
        thread_id=thread_id,
        assistant_id=request.assistant_id,
        metadata=request.metadata,
        multitask_strategy=request.multitask_strategy,
    )

    # 更新运行状态
    manager.runs.update(run.run_id, status="running")

    # 获取 DeerFlowClient
    client = manager.get_client()

    # 提取用户消息
    messages = []
    if request.input:
        if isinstance(request.input, dict):
            messages = request.input.get("messages", [])
        elif hasattr(request.input, "messages"):
            messages = request.input.messages

    user_message = extract_user_message(messages)

    # 处理 command（用于恢复中断的运行）
    if request.command and request.command.resume:
        # 恢复中断的运行
        user_message = str(request.command.resume)

    # 提取可配置参数
    # config 可能是 Config 对象或字典
    if request.config:
        if isinstance(request.config, dict):
            configurable = request.config.get("configurable", {})
        else:
            configurable = request.config.configurable or {}
    else:
        configurable = {}
    model_name = request.input.model_name if hasattr(request.input, 'model_name') else None
    thinking_enabled = request.input.thinking_enabled if hasattr(request.input, 'thinking_enabled') else None
    subagent_enabled = request.input.subagent_enabled if hasattr(request.input, 'subagent_enabled') else None
    plan_mode = request.input.plan_mode if hasattr(request.input, 'plan_mode') else None

    from fastapi.responses import StreamingResponse

    async def run_stream():
        """异步流生成器"""
        try:
            # 发送 metadata 事件
            yield SSEEventBuilder.metadata(run.run_id, thread_id)

            # 在线程池中运行同步的 stream 方法
            loop = asyncio.get_event_loop()

            # 构建 stream 参数
            stream_kwargs = {"thread_id": thread_id}
            if model_name or configurable.get("model_name"):
                stream_kwargs["model_name"] = model_name or configurable.get("model_name")
            if thinking_enabled is not None:
                stream_kwargs["thinking_enabled"] = thinking_enabled
            if subagent_enabled is not None:
                stream_kwargs["subagent_enabled"] = subagent_enabled
            if plan_mode is not None:
                stream_kwargs["plan_mode"] = plan_mode

            stream_generator = await loop.run_in_executor(
                None,
                lambda: client.stream(user_message, **stream_kwargs),
            )

            # 转换流事件
            async for event in deerflow_stream_to_langgraph_sse(
                stream_generator,
                run.run_id,
                thread_id,
            ):
                yield event

            # 更新运行状态
            manager.runs.update(run.run_id, status="success")

        except Exception as e:
            logger.exception("Run stream error")
            manager.runs.update(run.run_id, status="error")
            yield SSEEventBuilder.error(message=str(e), code="RUN_ERROR")
            yield SSEEventBuilder.end()

    return StreamingResponse(
        run_stream(),
        media_type="text/event-stream",
        headers=get_sse_headers(),
    )


@router.post("/runs/stream")
async def stream_run_stateless(request: RunStreamRequest):
    """
    无状态流式运行

    不需要 thread_id，会自动创建
    """
    manager = get_manager()

    # 创建临时线程
    thread = manager.threads.create()

    # 使用有状态的端点
    return await stream_run(thread.thread_id, request)


# ============== 后台运行 ==============


@router.post("/threads/{thread_id}/runs")
async def create_run(thread_id: str, request: RunCreateRequest):
    """
    创建后台运行

    完全兼容 LangGraph SDK runs.create()
    """
    manager = get_manager()

    # 确保线程存在
    thread = manager.threads.get(thread_id)
    if not thread:
        if request.if_not_exists == "reject":
            raise HTTPException(
                status_code=404,
                detail=f"Thread {thread_id} not found",
            )
        thread = manager.threads.create(thread_id=thread_id)

    # 创建运行记录
    run = manager.runs.create(
        thread_id=thread_id,
        assistant_id=request.assistant_id,
        metadata=request.metadata,
        multitask_strategy=request.multitask_strategy,
    )

    # 在后台启动运行
    asyncio.create_task(_run_background(run.run_id, thread_id, request))

    return Run(
        run_id=run.run_id,
        thread_id=run.thread_id,
        assistant_id=run.assistant_id,
        created_at=run.created_at,
        updated_at=run.updated_at,
        status=run.status,
        metadata=run.metadata,
        multitask_strategy=run.multitask_strategy,
    )


@router.post("/runs")
async def create_run_stateless(request: RunCreateRequest):
    """
    无状态创建后台运行

    不需要 thread_id，会自动创建
    """
    manager = get_manager()

    # 创建线程
    thread = manager.threads.create()

    return await create_run(thread.thread_id, request)


async def _run_background(run_id: str, thread_id: str, request: RunCreateRequest):
    """后台运行任务"""
    manager = get_manager()

    try:
        manager.runs.update(run_id, status="running")

        client = manager.get_client()

        # 提取用户消息
        messages = []
        if request.input:
            if isinstance(request.input, dict):
                messages = request.input.get("messages", [])
            elif hasattr(request.input, "messages"):
                messages = request.input.messages

        user_message = extract_user_message(messages)

        # 处理 command（用于恢复中断的运行）
        if request.command and request.command.resume:
            user_message = str(request.command.resume)

        # 同步执行
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: client.chat(user_message, thread_id),
        )

        manager.runs.update(run_id, status="success")

    except Exception as e:
        logger.exception("Background run error")
        manager.runs.update(run_id, status="error")
        manager.runs.update(run_id, metadata={"error": str(e)})


# ============== 等待运行 ==============


@router.post("/threads/{thread_id}/runs/wait")
async def wait_run(thread_id: str, request: RunWaitRequest):
    """
    创建运行并等待完成

    完全兼容 LangGraph SDK runs.wait()

    返回最终状态值
    """
    manager = get_manager()

    # 确保线程存在
    thread = manager.threads.get(thread_id)
    if not thread:
        if request.if_not_exists == "reject":
            raise HTTPException(
                status_code=404,
                detail=f"Thread {thread_id} not found",
            )
        thread = manager.threads.create(thread_id=thread_id)

    # 创建运行记录
    run = manager.runs.create(
        thread_id=thread_id,
        assistant_id=request.assistant_id,
        metadata=request.metadata,
        multitask_strategy=request.multitask_strategy,
    )

    # 更新运行状态
    manager.runs.update(run.run_id, status="running")

    try:
        client = manager.get_client()

        # 提取用户消息
        messages = []
        if request.input:
            if isinstance(request.input, dict):
                messages = request.input.get("messages", [])
            elif hasattr(request.input, "messages"):
                messages = request.input.messages

        user_message = extract_user_message(messages)

        # 处理 command（用于恢复中断的运行）
        if request.command and request.command.resume:
            user_message = str(request.command.resume)

        # 同步执行
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: client.chat(user_message, thread_id),
        )

        # 更新运行状态
        manager.runs.update(run.run_id, status="success")

        # 获取更新后的线程状态
        updated_thread = manager.threads.get(thread_id)
        if updated_thread:
            return updated_thread.values

        return {"messages": []}

    except Exception as e:
        logger.exception("Wait run error")
        manager.runs.update(run.run_id, status="error")

        if request.raise_error:
            raise HTTPException(
                status_code=500,
                detail=str(e),
            )

        return {"error": str(e)}


@router.post("/runs/wait")
async def wait_run_stateless(request: RunWaitRequest):
    """
    无状态等待运行

    不需要 thread_id，会自动创建
    """
    manager = get_manager()

    # 创建线程
    thread = manager.threads.create()

    return await wait_run(thread.thread_id, request)


# ============== 批量运行 ==============


@router.post("/runs/batch")
async def batch_create_runs(requests: list[RunCreateRequest]):
    """
    批量创建运行

    完全兼容 LangGraph SDK runs.batch()
    """
    manager = get_manager()
    results = []

    for req in requests:
        # 为每个请求创建线程
        thread = manager.threads.create()

        # 创建运行记录
        run = manager.runs.create(
            thread_id=thread.thread_id,
            assistant_id=req.assistant_id,
            metadata=req.metadata,
            multitask_strategy=req.multitask_strategy,
        )

        # 在后台启动
        asyncio.create_task(_run_background(run.run_id, thread.thread_id, req))

        results.append(
            Run(
                run_id=run.run_id,
                thread_id=run.thread_id,
                assistant_id=run.assistant_id,
                created_at=run.created_at,
                updated_at=run.updated_at,
                status=run.status,
                metadata=run.metadata,
                multitask_strategy=run.multitask_strategy,
            )
        )

    return results


# ============== 运行管理 ==============


@router.get("/threads/{thread_id}/runs")
async def list_runs(
    thread_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    select: list[str] | None = Query(default=None, description="选择返回的字段"),
):
    """
    列出线程的运行

    完全兼容 LangGraph SDK runs.list()
    """
    manager = get_manager()

    # 检查线程是否存在
    thread = manager.threads.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    runs = manager.runs.list_by_thread(
        thread_id=thread_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return [
        Run(
            run_id=r.run_id,
            thread_id=r.thread_id,
            assistant_id=r.assistant_id,
            created_at=r.created_at,
            updated_at=r.updated_at,
            status=r.status,
            metadata=r.metadata,
            multitask_strategy=r.multitask_strategy,
        )
        for r in runs
    ]


@router.get("/threads/{thread_id}/runs/{run_id}")
async def get_run(thread_id: str, run_id: str):
    """
    获取运行详情

    完全兼容 LangGraph SDK runs.get()
    """
    manager = get_manager()

    run = manager.runs.get(run_id)
    if not run or run.thread_id != thread_id:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return Run(
        run_id=run.run_id,
        thread_id=run.thread_id,
        assistant_id=run.assistant_id,
        created_at=run.created_at,
        updated_at=run.updated_at,
        status=run.status,
        metadata=run.metadata,
        multitask_strategy=run.multitask_strategy,
    )


@router.post("/threads/{thread_id}/runs/{run_id}/cancel")
async def cancel_run(
    thread_id: str,
    run_id: str,
    wait: int = Query(default=0),
    action: str = Query(default="interrupt"),
):
    """
    取消运行

    完全兼容 LangGraph SDK runs.cancel()

    Args:
        wait: 0=不等待, 1=等待完成
        action: interrupt(默认), rollback
    """
    manager = get_manager()

    run = manager.runs.get(run_id)
    if not run or run.thread_id != thread_id:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if run.status not in ("pending", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel run with status {run.status}",
        )

    # 更新状态为 interrupted
    manager.runs.update(run_id, status="interrupted")

    # TODO: 实际取消运行中的任务

    return None


@router.delete("/threads/{thread_id}/runs/{run_id}")
async def delete_run(thread_id: str, run_id: str):
    """
    删除运行

    完全兼容 LangGraph SDK runs.delete()
    """
    manager = get_manager()

    run = manager.runs.get(run_id)
    if not run or run.thread_id != thread_id:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # 只有完成的运行可以删除
    if run.status in ("pending", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete run with status {run.status}",
        )

    manager.runs.delete(run_id)

    return None


# ============== 批量取消 ==============


@router.post("/runs/cancel")
async def bulk_cancel_runs(
    request: dict,
    action: str = Query(default="interrupt"),
):
    """
    批量取消运行

    完全兼容 LangGraph SDK runs.cancel_many()

    Args:
        action: 取消动作，interrupt 或 rollback
    """
    manager = get_manager()

    thread_id = request.get("thread_id")
    run_ids = request.get("run_ids", [])
    status = request.get("status")

    if thread_id:
        # 取消指定线程的所有运行
        runs = manager.runs.list_by_thread(
            thread_id=thread_id,
            status=status if status else None,
            limit=1000,
        )
        for run in runs:
            if run.status in ("pending", "running"):
                manager.runs.update(run.run_id, status="interrupted")

    for run_id in run_ids:
        run = manager.runs.get(run_id)
        if run and run.status in ("pending", "running"):
            manager.runs.update(run_id, status="interrupted")

    return None


# ============== 加入运行 ==============


@router.get("/threads/{thread_id}/runs/{run_id}/join")
async def join_run(thread_id: str, run_id: str):
    """
    加入运行（等待完成）

    完全兼容 LangGraph SDK runs.join()
    """
    manager = get_manager()

    run = manager.runs.get(run_id)
    if not run or run.thread_id != thread_id:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # 等待运行完成
    max_wait = 300  # 5分钟超时
    waited = 0
    while run.status in ("pending", "running") and waited < max_wait:
        await asyncio.sleep(0.5)
        waited += 0.5
        run = manager.runs.get(run_id)
        if not run:
            break

    # 返回最终线程状态
    thread = manager.threads.get(thread_id)
    if thread:
        return thread.values

    return {"messages": []}


@router.get("/threads/{thread_id}/runs/{run_id}/stream")
async def join_run_stream(
    thread_id: str,
    run_id: str,
    stream_mode: str = Query(default="values"),
    cancel_on_disconnect: bool = Query(default=False),
    last_event_id: str | None = Query(default=None),
):
    """
    加入运行流

    完全兼容 LangGraph SDK runs.join_stream()
    """
    manager = get_manager()

    run = manager.runs.get(run_id)
    if not run or run.thread_id != thread_id:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    from fastapi.responses import StreamingResponse

    async def join_stream():
        """加入流生成器"""
        try:
            # 发送 metadata 事件
            yield SSEEventBuilder.metadata(run.run_id, thread_id)

            # 发送当前状态
            thread = manager.threads.get(thread_id)
            if thread:
                yield SSEEventBuilder.values(
                    messages=thread.values.get("messages", []),
                    title=thread.values.get("title"),
                )

            # 等待运行完成
            while run.status in ("pending", "running"):
                await asyncio.sleep(0.5)
                run = manager.runs.get(run_id)
                if not run:
                    break

            # 发送最终状态
            thread = manager.threads.get(thread_id)
            if thread:
                yield SSEEventBuilder.values(
                    messages=thread.values.get("messages", []),
                    title=thread.values.get("title"),
                )

            # 发送结束事件
            yield SSEEventBuilder.end()

        except Exception as e:
            logger.exception("Join stream error")
            yield SSEEventBuilder.error(message=str(e), code="JOIN_ERROR")
            yield SSEEventBuilder.end()

    return StreamingResponse(
        join_stream(),
        media_type="text/event-stream",
        headers=get_sse_headers(),
    )
