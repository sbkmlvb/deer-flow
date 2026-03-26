"""
SSE (Server-Sent Events) 流处理工具

提供与 LangGraph SDK 兼容的 SSE 事件格式化
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)


def format_sse_event(event_type: str, data: dict[str, Any] | None) -> str:
    """
    格式化单个 SSE 事件

    Args:
        event_type: 事件类型 (metadata, values, messages-tuple, end, error, etc.)
        data: 事件数据，None 表示空数据

    Returns:
        格式化的 SSE 字符串
    """
    if data is None:
        data = {}
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def format_sse_message(message: str) -> str:
    """
    格式化 SSE 消息（不带事件类型）

    Args:
        message: 消息内容

    Returns:
        格式化的 SSE 字符串
    """
    return f"data: {message}\n\n"


class SSEEventBuilder:
    """
    SSE 事件构建器

    提供便捷的方法构建各种类型的 SSE 事件
    """

    @staticmethod
    def metadata(run_id: str, thread_id: str | None = None) -> str:
        """
        构建 metadata 事件

        在流开始时发送，包含运行ID
        """
        data: dict[str, Any] = {"run_id": run_id}
        if thread_id:
            data["thread_id"] = thread_id
        return format_sse_event("metadata", data)

    @staticmethod
    def values(
        messages: list[dict[str, Any]] | None = None,
        title: str | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        **extra: Any,
    ) -> str:
        """
        构建 values 事件

        发送完整的状态快照
        """
        data: dict[str, Any] = {}
        if messages is not None:
            data["messages"] = messages
        if title is not None:
            data["title"] = title
        if artifacts is not None:
            data["artifacts"] = artifacts
        data.update(extra)
        return format_sse_event("values", data)

    @staticmethod
    def messages_tuple(
        msg_type: str,
        content: str = "",
        msg_id: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
        name: str | None = None,
        usage_metadata: dict[str, int] | None = None,
        **extra: Any,
    ) -> str:
        """
        构建 messages-tuple 事件

        发送单条消息的更新
        """
        data: dict[str, Any] = {"type": msg_type, "content": content}
        if msg_id:
            data["id"] = msg_id
        if tool_calls:
            data["tool_calls"] = tool_calls
        if tool_call_id:
            data["tool_call_id"] = tool_call_id
        if name:
            data["name"] = name
        if usage_metadata:
            data["usage_metadata"] = usage_metadata
        data.update(extra)
        return format_sse_event("messages-tuple", data)

    @staticmethod
    def ai_message(
        content: str,
        msg_id: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        usage_metadata: dict[str, int] | None = None,
    ) -> str:
        """构建 AI 消息事件"""
        return SSEEventBuilder.messages_tuple(
            msg_type="ai",
            content=content,
            msg_id=msg_id,
            tool_calls=tool_calls,
            usage_metadata=usage_metadata,
        )

    @staticmethod
    def tool_message(
        content: str,
        name: str,
        tool_call_id: str,
        msg_id: str | None = None,
    ) -> str:
        """构建工具消息事件"""
        return SSEEventBuilder.messages_tuple(
            msg_type="tool",
            content=content,
            msg_id=msg_id,
            name=name,
            tool_call_id=tool_call_id,
        )

    @staticmethod
    def human_message(
        content: str,
        msg_id: str | None = None,
    ) -> str:
        """构建人类消息事件"""
        return SSEEventBuilder.messages_tuple(
            msg_type="human",
            content=content,
            msg_id=msg_id,
        )

    @staticmethod
    def system_message(
        content: str,
        msg_id: str | None = None,
    ) -> str:
        """构建系统消息事件"""
        return SSEEventBuilder.messages_tuple(
            msg_type="system",
            content=content,
            msg_id=msg_id,
        )

    @staticmethod
    def updates(node_name: str, output: dict[str, Any]) -> str:
        """
        构建 updates 事件

        发送节点更新
        """
        return format_sse_event("updates", {node_name: output})

    @staticmethod
    def tasks(
        task_id: str,
        task_name: str,
        task_type: str = "start",  # start, result
        input_data: Any = None,
        result: Any = None,
        error: str | None = None,
        interrupts: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        构建 tasks 事件

        发送任务开始/结束事件
        """
        data: dict[str, Any] = {"id": task_id, "name": task_name}
        if task_type == "start":
            data["input"] = input_data
        elif task_type == "result":
            if result is not None:
                data["result"] = result
            if error:
                data["error"] = error
            if interrupts:
                data["interrupts"] = interrupts
        return format_sse_event("tasks", data)

    @staticmethod
    def checkpoints(checkpoint_data: dict[str, Any]) -> str:
        """
        构建 checkpoints 事件

        发送检查点事件
        """
        return format_sse_event("checkpoints", checkpoint_data)

    @staticmethod
    def debug(debug_data: dict[str, Any]) -> str:
        """
        构建 debug 事件

        发送调试信息
        """
        return format_sse_event("debug", debug_data)

    @staticmethod
    def custom(custom_data: Any) -> str:
        """
        构建 custom 事件

        发送自定义事件
        """
        return format_sse_event("custom", custom_data if isinstance(custom_data, dict) else {"data": custom_data})

    @staticmethod
    def error(message: str, code: str | None = None) -> str:
        """
        构建 error 事件

        发送错误信息
        """
        data: dict[str, Any] = {"message": message}
        if code:
            data["code"] = code
        return format_sse_event("error", data)

    @staticmethod
    def end(
        usage: dict[str, int] | None = None,
        **extra: Any,
    ) -> str:
        """
        构建 end 事件

        标记流结束
        """
        data: dict[str, Any] = {}
        if usage:
            data["usage"] = usage
        data.update(extra)
        return format_sse_event("end", data if data else None)


def get_sse_headers() -> dict[str, str]:
    """
    获取 SSE 响应的标准 HTTP 头

    Returns:
        SSE 响应头字典
    """
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Content-Type": "text/event-stream",
    }


async def deerflow_stream_to_langgraph_sse(
    stream_generator,
    run_id: str,
    thread_id: str,
) -> AsyncGenerator[str, None]:
    """
    将 DeerFlowClient.stream() 转换为 LangGraph SSE 格式

    Args:
        stream_generator: DeerFlowClient.stream() 返回的生成器
        run_id: 运行ID
        thread_id: 线程ID

    Yields:
        格式化的 SSE 事件字符串

    Note:
        线程状态（values/messages）由 LangGraph checkpointer 管理，
        ThreadStore.get() 会自动从 checkpointer 读取最新状态。
        这里只需要转发 SSE 事件，不需要手动同步状态。
    """
    # 首先发送 metadata 事件
    yield SSEEventBuilder.metadata(run_id, thread_id)

    try:
        for event in stream_generator:
            event_type = event.type
            event_data = event.data if hasattr(event, "data") else {}

            if event_type == "values":
                # values 事件包含完整状态快照
                yield SSEEventBuilder.values(
                    messages=event_data.get("messages"),
                    title=event_data.get("title"),
                    artifacts=event_data.get("artifacts"),
                )
            elif event_type == "messages-tuple":
                # messages-tuple 事件包含单条消息
                # LangGraph SDK 期望格式: event: "messages", data: [message, metadata]
                # event_data 是消息对象，需要包装成数组格式
                yield format_sse_event("messages", [event_data, {"tags": []}])
            elif event_type == "end":
                # end 事件标记流结束
                # 状态由 checkpointer 管理，不需要手动同步
                yield SSEEventBuilder.end(usage=event_data.get("usage"))
            elif event_type == "error":
                # error 事件
                yield SSEEventBuilder.error(
                    message=event_data.get("message", "Unknown error"),
                    code=event_data.get("code"),
                )
            else:
                # 其他事件类型直接转发
                yield format_sse_event(event_type, event_data)

    except Exception as e:
        logger.exception("Stream error")
        yield SSEEventBuilder.error(message=str(e), code="STREAM_ERROR")
        yield SSEEventBuilder.end()


def extract_user_message(messages: list[dict]) -> str:
    """
    从消息列表中提取最后一条用户消息

    Args:
        messages: 消息列表

    Returns:
        用户消息文本，如果没有则返回空字符串
    """
    for msg in reversed(messages):
        msg_type = msg.get("type", "")
        role = msg.get("role", "")

        # 检查是否是用户消息
        if msg_type == "human" or role in ("user", "human"):
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


def serialize_message(msg: dict) -> dict[str, Any]:
    """
    序列化消息为 LangGraph 格式

    Args:
        msg: 消息字典

    Returns:
        序列化后的消息字典
    """
    result: dict[str, Any] = {
        "type": msg.get("type", "unknown"),
        "content": msg.get("content", ""),
    }
    if msg.get("id"):
        result["id"] = msg["id"]
    if msg.get("tool_calls"):
        result["tool_calls"] = msg["tool_calls"]
    if msg.get("tool_call_id"):
        result["tool_call_id"] = msg["tool_call_id"]
    if msg.get("name"):
        result["name"] = msg["name"]
    if msg.get("usage_metadata"):
        result["usage_metadata"] = msg["usage_metadata"]
    if msg.get("additional_kwargs"):
        result["additional_kwargs"] = msg["additional_kwargs"]
    return result
