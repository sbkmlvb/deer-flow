"""
Assistants API 路由

实现与 LangGraph SDK 完全兼容的助手管理 API
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .schemas import (
    Assistant,
    AssistantCreateRequest,
    AssistantSearchRequest,
    AssistantUpdateRequest,
    Config,
    GraphResponse,
    GraphSchema,
    get_current_timestamp,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistants", tags=["langgraph-assistants"])


# ============== 内置助手 ==============

# 默认助手列表 - DeerFlow 只有一个 lead_agent
DEFAULT_ASSISTANTS = {
    "lead_agent": {
        "assistant_id": "lead_agent",
        "graph_id": "lead_agent",
        "name": "Lead Agent",
        "description": "DeerFlow 主代理，支持工具调用、沙箱执行、记忆管理等高级功能",
        "config": {},
        "context": {},
        "metadata": {"created_by": "system"},
        "version": 1,
    }
}


# ============== 助手 CRUD ==============


@router.get("")
async def list_assistants(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    列出助手

    完全兼容 LangGraph SDK assistants.list()
    """
    assistants = []
    for assistant_id, data in DEFAULT_ASSISTANTS.items():
        now = get_current_timestamp()
        assistants.append(
            Assistant(
                assistant_id=data["assistant_id"],
                graph_id=data["graph_id"],
                name=data["name"],
                description=data["description"],
                config=data["config"],
                context=data["context"],
                created_at=now,
                updated_at=now,
                metadata=data["metadata"],
                version=data["version"],
            )
        )

    return assistants[offset : offset + limit]


@router.get("/{assistant_id}")
async def get_assistant(assistant_id: str):
    """
    获取助手详情

    完全兼容 LangGraph SDK assistants.get()
    """
    if assistant_id not in DEFAULT_ASSISTANTS:
        raise HTTPException(
            status_code=404,
            detail=f"Assistant {assistant_id} not found",
        )

    data = DEFAULT_ASSISTANTS[assistant_id]
    now = get_current_timestamp()

    return Assistant(
        assistant_id=data["assistant_id"],
        graph_id=data["graph_id"],
        name=data["name"],
        description=data["description"],
        config=data["config"],
        context=data["context"],
        created_at=now,
        updated_at=now,
        metadata=data["metadata"],
        version=data["version"],
    )


@router.post("")
async def create_assistant(request: AssistantCreateRequest):
    """
    创建助手

    完全兼容 LangGraph SDK assistants.create()

    注意：DeerFlow 当前只支持内置的 lead_agent，
    此端点主要用于兼容性，返回已有助手或创建占位符
    """
    assistant_id = request.assistant_id or str(uuid.uuid4())
    graph_id = request.graph_id or assistant_id

    # 检查冲突
    if assistant_id in DEFAULT_ASSISTANTS:
        if request.if_exists == "raise":
            raise HTTPException(
                status_code=409,
                detail=f"Assistant {assistant_id} already exists",
            )
        elif request.if_exists == "do_nothing":
            return await get_assistant(assistant_id)

    now = get_current_timestamp()

    return Assistant(
        assistant_id=assistant_id,
        graph_id=graph_id,
        name=request.name or assistant_id,
        description=request.description,
        config=request.config or {},
        context=request.context or {},
        created_at=now,
        updated_at=now,
        metadata=request.metadata or {},
        version=1,
    )


@router.patch("/{assistant_id}")
async def update_assistant(assistant_id: str, request: AssistantUpdateRequest):
    """
    更新助手

    完全兼容 LangGraph SDK assistants.update()
    """
    if assistant_id not in DEFAULT_ASSISTANTS:
        raise HTTPException(
            status_code=404,
            detail=f"Assistant {assistant_id} not found",
        )

    data = DEFAULT_ASSISTANTS[assistant_id].copy()

    # 应用更新
    if request.graph_id is not None:
        data["graph_id"] = request.graph_id
    if request.config is not None:
        data["config"] = request.config
    if request.context is not None:
        data["context"] = request.context
    if request.metadata is not None:
        data["metadata"].update(request.metadata)
    if request.name is not None:
        data["name"] = request.name
    if request.description is not None:
        data["description"] = request.description

    data["version"] = data.get("version", 1) + 1
    now = get_current_timestamp()

    return Assistant(
        assistant_id=data["assistant_id"],
        graph_id=data["graph_id"],
        name=data["name"],
        description=data["description"],
        config=data["config"],
        context=data["context"],
        created_at=now,
        updated_at=now,
        metadata=data["metadata"],
        version=data["version"],
    )


@router.delete("/{assistant_id}")
async def delete_assistant(
    assistant_id: str,
    delete_threads: bool = Query(default=False),
):
    """
    删除助手

    完全兼容 LangGraph SDK assistants.delete()

    注意：DeerFlow 不允许删除内置的 lead_agent
    """
    if assistant_id in DEFAULT_ASSISTANTS:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete built-in assistant {assistant_id}",
        )

    # 非内置助手可以直接删除（当前不存在）
    return None


@router.post("/search")
async def search_assistants(request: AssistantSearchRequest | None = None):
    """
    搜索助手

    完全兼容 LangGraph SDK assistants.search()
    """
    if request is None:
        request = AssistantSearchRequest()

    results = []
    for assistant_id, data in DEFAULT_ASSISTANTS.items():
        # 元数据过滤
        if request.metadata:
            match = all(
                data["metadata"].get(k) == v for k, v in request.metadata.items()
            )
            if not match:
                continue

        # graph_id 过滤
        if request.graph_id and data["graph_id"] != request.graph_id:
            continue

        # 名称过滤（模糊匹配）
        if request.name and request.name.lower() not in data["name"].lower():
            continue

        now = get_current_timestamp()
        results.append(
            Assistant(
                assistant_id=data["assistant_id"],
                graph_id=data["graph_id"],
                name=data["name"],
                description=data["description"],
                config=data["config"],
                context=data["context"],
                created_at=now,
                updated_at=now,
                metadata=data["metadata"],
                version=data["version"],
            )
        )

    return results[request.offset : request.offset + request.limit]


# ============== 助手图 ==============


@router.get("/{assistant_id}/graph")
async def get_assistant_graph(
    assistant_id: str,
    xray: int | None = Query(default=None),
):
    """
    获取助手图

    完全兼容 LangGraph SDK assistants.get_graph()

    返回图的节点和边
    """
    if assistant_id not in DEFAULT_ASSISTANTS:
        raise HTTPException(
            status_code=404,
            detail=f"Assistant {assistant_id} not found",
        )

    # 返回简化的图结构
    # 实际实现应该从 LangGraph 获取真实图结构
    return GraphResponse(
        nodes=[
            {"id": "__start__", "type": "entry", "name": "Start"},
            {"id": "agent", "type": "node", "name": "Agent"},
            {"id": "tools", "type": "node", "name": "Tools"},
            {"id": "__end__", "type": "exit", "name": "End"},
        ],
        edges=[
            {"source": "__start__", "target": "agent"},
            {"source": "agent", "target": "tools", "conditional": True},
            {"source": "agent", "target": "__end__", "conditional": True},
            {"source": "tools", "target": "agent"},
        ],
    )


@router.get("/{assistant_id}/schemas")
async def get_assistant_schemas(assistant_id: str):
    """
    获取助手 Schema

    完全兼容 LangGraph SDK assistants.get_schemas()
    """
    if assistant_id not in DEFAULT_ASSISTANTS:
        raise HTTPException(
            status_code=404,
            detail=f"Assistant {assistant_id} not found",
        )

    return GraphSchema(
        graph_id=assistant_id,
        input_schema={
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                }
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {"type": "object"},
                }
            },
        },
        state_schema={
            "type": "object",
            "properties": {
                "messages": {"type": "array"},
                "sandbox": {"type": "object"},
                "thread_data": {"type": "object"},
                "title": {"type": "string"},
                "artifacts": {"type": "array"},
            },
        },
        config_schema={
            "type": "object",
            "properties": {
                "configurable": {
                    "type": "object",
                    "properties": {
                        "model_name": {"type": "string"},
                        "thinking_enabled": {"type": "boolean"},
                        "is_plan_mode": {"type": "boolean"},
                        "subagent_enabled": {"type": "boolean"},
                    },
                }
            },
        },
        context_schema=None,
    )


# ============== 子图 ==============


@router.get("/{assistant_id}/subgraphs")
async def list_subgraphs(
    assistant_id: str,
    recurse: bool = Query(default=False),
):
    """
    列出子图

    完全兼容 LangGraph SDK assistants.get_subgraphs()
    """
    if assistant_id not in DEFAULT_ASSISTANTS:
        raise HTTPException(
            status_code=404,
            detail=f"Assistant {assistant_id} not found",
        )

    # DeerFlow 当前没有子图
    return {}


@router.get("/{assistant_id}/subgraphs/{namespace:path}")
async def get_subgraph(
    assistant_id: str,
    namespace: str,
    recurse: bool = Query(default=False),
):
    """
    获取子图

    完全兼容 LangGraph SDK assistants.get_subgraph()
    """
    if assistant_id not in DEFAULT_ASSISTANTS:
        raise HTTPException(
            status_code=404,
            detail=f"Assistant {assistant_id} not found",
        )

    raise HTTPException(
        status_code=404,
        detail=f"Subgraph {namespace} not found",
    )


# ============== 统计 ==============


@router.post("/count")
async def count_assistants(request: dict | None = None):
    """
    统计助手数量

    完全兼容 LangGraph SDK assistants.count()
    """
    if request is None:
        request = {}

    count = 0
    for assistant_id, data in DEFAULT_ASSISTANTS.items():
        # 元数据过滤
        if "metadata" in request:
            match = all(
                data["metadata"].get(k) == v
                for k, v in request["metadata"].items()
            )
            if not match:
                continue

        # graph_id 过滤
        if "graph_id" in request and data["graph_id"] != request["graph_id"]:
            continue

        # 名称过滤
        if "name" in request and request["name"].lower() not in data["name"].lower():
            continue

        count += 1

    return count


# ============== 版本管理 ==============


@router.post("/{assistant_id}/versions")
async def get_assistant_versions(
    assistant_id: str,
    request: dict | None = None,
):
    """
    获取助手版本列表

    完全兼容 LangGraph SDK assistants.get_versions()
    """
    if assistant_id not in DEFAULT_ASSISTANTS:
        raise HTTPException(
            status_code=404,
            detail=f"Assistant {assistant_id} not found",
        )

    if request is None:
        request = {}

    data = DEFAULT_ASSISTANTS[assistant_id]
    now = get_current_timestamp()
    limit = request.get("limit", 10)
    offset = request.get("offset", 0)

    # DeerFlow 当前只有一个版本
    versions = [
        Assistant(
            assistant_id=data["assistant_id"],
            graph_id=data["graph_id"],
            name=data["name"],
            description=data["description"],
            config=data["config"],
            context=data["context"],
            created_at=now,
            updated_at=now,
            metadata=data["metadata"],
            version=data["version"],
        )
    ]

    return versions[offset : offset + limit]


@router.post("/{assistant_id}/latest")
async def set_assistant_latest(
    assistant_id: str,
    request: dict,
):
    """
    设置助手最新版本

    完全兼容 LangGraph SDK assistants.set_latest()
    """
    if assistant_id not in DEFAULT_ASSISTANTS:
        raise HTTPException(
            status_code=404,
            detail=f"Assistant {assistant_id} not found",
        )

    version = request.get("version")
    if version is None:
        raise HTTPException(
            status_code=400,
            detail="Version is required",
        )

    data = DEFAULT_ASSISTANTS[assistant_id]
    now = get_current_timestamp()

    # DeerFlow 当前只支持版本 1
    if version != 1:
        raise HTTPException(
            status_code=400,
            detail=f"Version {version} not found",
        )

    return Assistant(
        assistant_id=data["assistant_id"],
        graph_id=data["graph_id"],
        name=data["name"],
        description=data["description"],
        config=data["config"],
        context=data["context"],
        created_at=now,
        updated_at=now,
        metadata=data["metadata"],
        version=data["version"],
    )
