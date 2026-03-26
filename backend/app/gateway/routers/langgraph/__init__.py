"""
LangGraph 兼容层路由模块

提供与 LangGraph SDK 完全兼容的 API 端点

架构说明：
- schemas.py: 所有数据模型定义（Pydantic）
- client.py: 客户端管理器、线程存储、运行存储
- persistence.py: JSON文件持久化存储
- sse.py: SSE 流处理工具
- threads.py: Threads API 路由
- runs.py: Runs API 路由
- assistants.py: Assistants API 路由
- store.py: Store API 路由（跨线程存储）
- cron.py: Cron API 路由（定时任务）

使用：
    from app.gateway.routers.langgraph import router as langgraph_router
    app.include_router(langgraph_router)

    # 路由自动注册在 /api/langgraph/* 路径下
"""

from fastapi import APIRouter

from .assistants import router as assistants_router
from .cron import router as cron_router
from .runs import router as runs_router
from .store import router as store_router
from .threads import router as threads_router

# 主路由器 - 使用 /api/langgraph 前缀以兼容前端
router = APIRouter(prefix="/api/langgraph", tags=["langgraph"])

# 注册子路由
# Threads API - /threads
router.include_router(threads_router)

# Runs API - /threads/{thread_id}/runs 和 /runs
router.include_router(runs_router)

# Assistants API - /assistants
router.include_router(assistants_router)

# Store API - /store
router.include_router(store_router)

# Cron API - /cron
router.include_router(cron_router)


# ============== 健康检查 ==============


@router.get("/health")
async def health_check():
    """
    LangGraph 兼容层健康检查
    """
    return {"status": "ok", "service": "langgraph-compat"}


@router.get("/info")
async def get_info():
    """
    获取信息

    兼容 LangGraph Server 的 /info 端点
    """
    return {
        "version": "1.0.0",
        "compatibility": "langgraph-sdk",
        "features": [
            "threads",
            "runs",
            "assistants",
            "store",
            "cron",
            "streaming",
        ],
    }


# 导出公共接口
__all__ = [
    "router",
    "threads_router",
    "runs_router",
    "assistants_router",
    "store_router",
    "cron_router",
]
