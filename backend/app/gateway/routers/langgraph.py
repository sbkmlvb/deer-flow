"""
LangGraph 兼容 API 路由
使用 DeerFlowClient 嵌入式客户端实现，无需独立的 LangGraph Server

架构说明：
==========
本模块提供与 LangGraph Server 完全兼容的 API 端点，但在进程内使用 DeerFlowClient
运行 Agent，而不是通过 HTTP 调用独立的 LangGraph Server。

优势：
1. 单进程部署 - 只需运行 Gateway，无需独立的 LangGraph Server
2. 零网络延迟 - 进程内调用，无 HTTP 往返
3. 简化打包 - 只需打包一个可执行文件
4. 资源效率 - 共享内存和配置，减少资源占用

实现原理：
- DeerFlowClient 导入 deerflow 模块，与 LangGraph Server 共享代码
- 使用 asyncio.run_in_executor() 在线程池中运行同步方法
- SSE 流格式与 LangGraph Server 完全兼容

API 端点：
/api/langgraph/threads                     - 线程管理 (CRUD)
/api/langgraph/threads/{id}/runs           - 运行管理
/api/langgraph/threads/{id}/runs/stream    - 流式对话 (SSE)
/api/langgraph/threads/{id}/runs/wait      - 同步对话
/api/langgraph/assistants                  - 助手列表

兼容性：
前端无需修改，API 格式与 @langchain/langgraph-sdk 完全兼容
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from deerflow.client import DeerFlowClient

logger = logging.getLogger(__name__)

# 路由前缀使用 /api/langgraph 以兼容前端
router = APIRouter(prefix="/api/langgraph", tags=["langgraph"])

# 全局客户端实例（延迟初始化）
_client: DeerFlowClient | None = None


def get_client() -> DeerFlowClient:
    """获取或创建 DeerFlowClient 实例"""
    global _client
    if _client is None:
        _client = DeerFlowClient()
    return _client


def reset_client():
    """重置客户端实例（配置变更后调用）"""
    global _client
    _client = None


# ============== 请求/响应模型 ==============


class RunInput(BaseModel):
    """运行输入"""

    messages: list[dict] = Field(default_factory=list, description="消息列表")
    model_name: str | None = Field(default=None, description="模型名称")
    thinking_enabled: bool = Field(default=True, description="启用思考模式")
    subagent_enabled: bool = Field(default=False, description="启用子代理")
    plan_mode: bool = Field(default=False, description="计划模式")


class ThreadCreateRequest(BaseModel):
    """创建线程请求"""

    thread_id: str | None = Field(default=None, description="线程ID（可选）")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")


class ThreadCreateResponse(BaseModel):
    """创建线程响应"""

    thread_id: str
    created_at: str
    metadata: dict[str, Any] | None = None


class ThreadStateResponse(BaseModel):
    """线程状态响应"""

    values: dict[str, Any]
    next: list[str] = Field(default_factory=list)
    created_at: str | None = None
    metadata: dict[str, Any] | None = None


class ThreadsListResponse(BaseModel):
    """线程列表响应"""

    threads: list[dict[str, Any]]


class RunCreateRequest(BaseModel):
    """创建运行请求"""

    assistant_id: str = Field(default="lead_agent", description="助手ID")
    input: RunInput = Field(default_factory=RunInput, description="输入")
    config: dict[str, Any] | None = Field(default=None, description="配置")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")
    multitask_strategy: str | None = Field(default=None, description="多任务策略")
    webhook: str | None = Field(default=None, description="Webhook URL")


class RunStreamRequest(BaseModel):
    """流式运行请求"""

    assistant_id: str = Field(default="lead_agent", description="助手ID")
    input: RunInput = Field(default_factory=RunInput, description="输入")
    config: dict[str, Any] | None = Field(default=None, description="配置")


# ============== 辅助函数 ==============


def _extract_user_message(messages: list[dict]) -> str:
    """从消息列表中提取最后一条用户消息"""
    for msg in reversed(messages):
        msg_type = msg.get("type", "")
        role = msg.get("role", "")
        if msg_type == "human" or role == "user" or role == "human":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # 处理多模态内容
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                return " ".join(text_parts)
    return ""


def _format_sse_event(event_type: str, data: dict) -> str:
    """格式化 SSE 事件"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ============== 线程 API ==============


@router.post("/threads", response_model=ThreadCreateResponse)
async def create_thread(request: ThreadCreateRequest | None = None):
    """创建新线程"""
    thread_id = request.thread_id if request and request.thread_id else str(uuid.uuid4())
    return ThreadCreateResponse(
        thread_id=thread_id,
        created_at="",
        metadata=request.metadata if request else None,
    )


@router.get("/threads/{thread_id}", response_model=ThreadStateResponse)
async def get_thread_state(thread_id: str):
    """获取线程状态"""
    # DeerFlowClient 不直接支持获取历史状态，返回空状态
    return ThreadStateResponse(
        values={"messages": []},
        next=[],
        created_at=None,
        metadata={"thread_id": thread_id},
    )


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    """删除线程"""
    return {"success": True, "thread_id": thread_id}


@router.get("/threads", response_model=ThreadsListResponse)
async def list_threads():
    """列出线程"""
    # DeerFlowClient 不维护线程列表，返回空列表
    return ThreadsListResponse(threads=[])


# ============== 运行 API ==============


@router.post("/threads/{thread_id}/runs")
async def create_run(thread_id: str, request: RunCreateRequest):
    """创建运行（非流式）"""
    try:
        client = get_client()

        # 提取用户消息
        user_message = _extract_user_message(request.input.messages)
        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found in input")

        # 获取配置
        config = request.config or {}
        configurable = config.get("configurable", {})

        # 同步调用 chat
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat(
                user_message,
                thread_id=thread_id,
                model_name=request.input.model_name or configurable.get("model_name"),
                thinking_enabled=request.input.thinking_enabled,
                subagent_enabled=request.input.subagent_enabled,
                plan_mode=request.input.plan_mode,
            ),
        )

        return {
            "run_id": str(uuid.uuid4()),
            "thread_id": thread_id,
            "assistant_id": request.assistant_id,
            "status": "success",
            "response": response,
        }

    except Exception as e:
        logger.exception("Run failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/threads/{thread_id}/runs/stream")
async def create_run_stream(thread_id: str, request: RunStreamRequest):
    """创建流式运行"""
    try:
        # 提取用户消息
        user_message = _extract_user_message(request.input.messages)
        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found in input")

        # 获取配置
        config = request.config or {}
        configurable = config.get("configurable", {})

        async def generate_sse() -> AsyncGenerator[str, None]:
            """生成 SSE 流"""
            client = get_client()

            # 在线程池中运行同步的 stream 方法
            loop = asyncio.get_event_loop()

            def stream_generator():
                return client.stream(
                    user_message,
                    thread_id=thread_id,
                    model_name=request.input.model_name or configurable.get("model_name"),
                    thinking_enabled=request.input.thinking_enabled,
                    subagent_enabled=request.input.subagent_enabled,
                    plan_mode=request.input.plan_mode,
                )

            # 获取生成器
            stream_gen = await loop.run_in_executor(None, stream_generator)

            # 遍历事件
            for event in stream_gen:
                # 转换为 LangGraph SSE 格式
                if event.type == "values":
                    yield _format_sse_event("values", event.data)
                elif event.type == "messages-tuple":
                    yield _format_sse_event("messages-tuple", event.data)
                elif event.type == "end":
                    yield _format_sse_event("end", event.data)

        return StreamingResponse(
            generate_sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        logger.exception("Stream failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/threads/{thread_id}/runs/wait")
async def create_run_wait(thread_id: str, request: RunCreateRequest):
    """创建运行并等待完成"""
    try:
        client = get_client()

        # 提取用户消息
        user_message = _extract_user_message(request.input.messages)
        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found in input")

        # 获取配置
        config = request.config or {}
        configurable = config.get("configurable", {})

        # 同步调用 chat
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat(
                user_message,
                thread_id=thread_id,
                model_name=request.input.model_name or configurable.get("model_name"),
                thinking_enabled=request.input.thinking_enabled,
                subagent_enabled=request.input.subagent_enabled,
                plan_mode=request.input.plan_mode,
            ),
        )

        # 构建响应（模拟 LangGraph 格式）
        return {
            "run_id": str(uuid.uuid4()),
            "thread_id": thread_id,
            "assistant_id": request.assistant_id,
            "status": "success",
            "values": {
                "messages": [
                    {
                        "type": "ai",
                        "content": response,
                        "id": str(uuid.uuid4()),
                    }
                ]
            },
        }

    except Exception as e:
        logger.exception("Run wait failed")
        raise HTTPException(status_code=500, detail=str(e))


# ============== 助手 API ==============


@router.get("/assistants")
async def list_assistants():
    """列出可用助手"""
    return {
        "assistants": [
            {
                "assistant_id": "lead_agent",
                "graph_id": "lead_agent",
                "name": "Lead Agent",
                "description": "DeerFlow 主代理",
                "config": {},
            }
        ]
    }


@router.get("/assistants/{assistant_id}")
async def get_assistant(assistant_id: str):
    """获取助手详情"""
    if assistant_id != "lead_agent":
        raise HTTPException(status_code=404, detail=f"Assistant {assistant_id} not found")

    return {
        "assistant_id": "lead_agent",
        "graph_id": "lead_agent",
        "name": "Lead Agent",
        "description": "DeerFlow 主代理",
        "config": {},
    }
