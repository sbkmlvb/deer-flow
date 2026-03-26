"""
Store API 路由

实现与 LangGraph SDK 完全兼容的跨线程存储 API
"""

import logging
import threading
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .persistence import JSONFileStore
from .schemas import (
    StoreItem,
    StorePutRequest,
    StoreSearchRequest,
    get_current_timestamp,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/store", tags=["langgraph-store"])


class StoreManager:
    """
    存储管理器

    实现跨线程的键值存储，支持命名空间和过滤搜索
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

            store_path = Path(get_paths().base_dir) / "store" / "items.json"
        except ImportError:
            store_path = Path(".deer-flow/store/items.json")

        self._store = JSONFileStore(store_path)
        self._data_lock = threading.Lock()
        self._initialized = True

    def _get_item_key(self, namespace: list[str], key: str) -> str:
        """生成唯一存储键"""
        namespace_str = ".".join(namespace) if namespace else "_root"
        return f"{namespace_str}:{key}"

    def put_item(
        self,
        namespace: list[str],
        key: str,
        value: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """存储或更新项目"""
        # 验证namespace不能包含点号
        for label in namespace:
            if "." in label:
                raise ValueError(
                    f"Invalid namespace label '{label}'. "
                    "Namespace labels cannot contain periods ('.')."
                )

        with self._data_lock:
            store_key = self._get_item_key(namespace, key)
            now = get_current_timestamp()

            # 获取现有项目以保留created_at
            existing = self._store.get(store_key)
            if existing:
                created_at = existing.get("created_at", now)
            else:
                created_at = now

            item = {
                "namespace": namespace,
                "key": key,
                "value": value,
                "created_at": created_at,
                "updated_at": now,
            }

            if ttl is not None:
                item["ttl"] = ttl
                item["expires_at"] = time.time() + (ttl * 60)

            self._store.set(store_key, item)

    def get_item(
        self,
        namespace: list[str],
        key: str,
        refresh_ttl: bool | None = None,
    ) -> StoreItem | None:
        """获取单个项目"""
        with self._data_lock:
            store_key = self._get_item_key(namespace, key)
            item = self._store.get(store_key)

            if not item:
                return None

            # 检查是否过期
            if self._is_expired(item):
                self._store.delete(store_key)
                return None

            # 刷新TTL
            if refresh_ttl and "ttl" in item:
                item["expires_at"] = time.time() + (item["ttl"] * 60)
                item["updated_at"] = get_current_timestamp()
                self._store.set(store_key, item)

            return StoreItem(
                namespace=item["namespace"],
                key=item["key"],
                value=item["value"],
                created_at=item["created_at"],
                updated_at=item["updated_at"],
            )

    def delete_item(self, namespace: list[str], key: str) -> bool:
        """删除项目"""
        with self._data_lock:
            store_key = self._get_item_key(namespace, key)
            return self._store.delete(store_key)

    def search_items(
        self,
        namespace_prefix: list[str],
        filter: dict[str, Any] | None = None,
        limit: int = 10,
        offset: int = 0,
        query: str | None = None,
        refresh_ttl: bool | None = None,
    ) -> list[StoreItem]:
        """搜索项目"""
        results = []

        with self._data_lock:
            all_data = self._store.values()

            for store_key, item in all_data.items():
                if not isinstance(item, dict):
                    continue

                # 检查命名空间前缀
                ns = item.get("namespace", [])
                if not self._namespace_matches_prefix(ns, namespace_prefix):
                    continue

                # 检查是否过期
                if self._is_expired(item):
                    self._store.delete(store_key)
                    continue

                # 应用过滤器
                if filter:
                    value = item.get("value", {})
                    if not self._matches_filter(value, filter):
                        continue

                # 刷新TTL
                if refresh_ttl and "ttl" in item:
                    item["expires_at"] = time.time() + (item["ttl"] * 60)
                    item["updated_at"] = get_current_timestamp()
                    self._store.set(store_key, item)

                results.append(
                    StoreItem(
                        namespace=item["namespace"],
                        key=item["key"],
                        value=item["value"],
                        created_at=item["created_at"],
                        updated_at=item["updated_at"],
                    )
                )

        # 按更新时间排序（最新的在前）
        results.sort(key=lambda x: x.updated_at, reverse=True)

        return results[offset : offset + limit]

    def list_namespaces(
        self,
        prefix: list[str] | None = None,
        suffix: list[str] | None = None,
        max_depth: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[list[str]]:
        """列出命名空间"""
        namespaces = set()

        with self._data_lock:
            all_data = self._store.values()

            for item in all_data.values():
                if not isinstance(item, dict):
                    continue

                ns = item.get("namespace", [])

                # 检查前缀
                if prefix and not self._namespace_matches_prefix(ns, prefix):
                    continue

                # 检查后缀
                if suffix and not self._namespace_matches_suffix(ns, suffix):
                    continue

                # 应用深度限制
                if max_depth is not None and len(ns) > max_depth:
                    ns = ns[:max_depth]

                namespaces.add(tuple(ns))

        # 转换为列表并排序
        result = [list(ns) for ns in sorted(namespaces)]

        return result[offset : offset + limit]

    def _namespace_matches_prefix(
        self,
        namespace: list[str],
        prefix: list[str],
    ) -> bool:
        """检查命名空间是否匹配前缀"""
        if not prefix:
            return True
        if len(namespace) < len(prefix):
            return False
        return namespace[: len(prefix)] == prefix

    def _namespace_matches_suffix(
        self,
        namespace: list[str],
        suffix: list[str],
    ) -> bool:
        """检查命名空间是否匹配后缀"""
        if not suffix:
            return True
        if len(namespace) < len(suffix):
            return False
        return namespace[-len(suffix) :] == suffix

    def _matches_filter(
        self,
        value: dict[str, Any],
        filter: dict[str, Any],
    ) -> bool:
        """检查值是否匹配过滤条件"""
        for key, filter_value in filter.items():
            if "." in key:
                # 支持嵌套路径 (e.g., "user.name")
                parts = key.split(".")
                current = value
                for part in parts[:-1]:
                    if not isinstance(current, dict) or part not in current:
                        return False
                    current = current[part]
                if current.get(parts[-1]) != filter_value:
                    return False
            else:
                if value.get(key) != filter_value:
                    return False
        return True

    def _is_expired(self, item: dict[str, Any]) -> bool:
        """检查项目是否已过期"""
        if "expires_at" not in item:
            return False
        return time.time() > item["expires_at"]


def get_store_manager() -> StoreManager:
    """获取存储管理器单例"""
    return StoreManager()


# ============== API 端点 ==============


@router.put("/items")
async def put_store_item(request: StorePutRequest):
    """
    存储或更新项目

    完全兼容 LangGraph SDK store.put_item()
    """
    manager = get_store_manager()

    try:
        manager.put_item(
            namespace=request.namespace,
            key=request.key,
            value=request.value,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return None


@router.get("/items")
async def get_store_item(
    key: str = Query(..., description="项目唯一标识"),
    namespace: str = Query(..., description="命名空间（点分隔）"),
    refresh_ttl: bool | None = Query(default=None, description="是否刷新TTL"),
):
    """
    获取单个项目

    完全兼容 LangGraph SDK store.get_item()
    """
    manager = get_store_manager()

    namespace_list = namespace.split(".") if namespace else []

    item = manager.get_item(
        namespace=namespace_list,
        key=key,
        refresh_ttl=refresh_ttl,
    )

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return item


@router.delete("/items")
async def delete_store_item(request: dict):
    """
    删除项目

    完全兼容 LangGraph SDK store.delete_item()
    """
    manager = get_store_manager()

    namespace = request.get("namespace", [])
    key = request.get("key")

    if not key:
        raise HTTPException(status_code=400, detail="Key is required")

    success = manager.delete_item(namespace=namespace, key=key)

    # LangGraph SDK 在项目不存在时也返回成功
    return None


@router.post("/items/search")
async def search_store_items(request: StoreSearchRequest):
    """
    搜索项目

    完全兼容 LangGraph SDK store.search_items()

    返回格式: {"items": [...]}
    """
    manager = get_store_manager()

    items = manager.search_items(
        namespace_prefix=request.namespace or [],
        filter=request.filter,
        limit=request.limit,
        offset=request.offset,
    )

    return {"items": items}


@router.post("/namespaces")
async def list_store_namespaces(request: dict):
    """
    列出命名空间

    完全兼容 LangGraph SDK store.list_namespaces()

    返回命名空间列表
    """
    manager = get_store_manager()

    namespaces = manager.list_namespaces(
        prefix=request.get("prefix"),
        suffix=request.get("suffix"),
        max_depth=request.get("max_depth"),
        limit=request.get("limit", 100),
        offset=request.get("offset", 0),
    )

    return namespaces
