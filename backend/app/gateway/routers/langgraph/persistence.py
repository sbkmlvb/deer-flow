"""
持久化存储基类

使用JSON文件实现原子写入的持久化存储
"""

import json
import logging
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class JSONFileStore:
    """
    JSON文件持久化存储

    使用原子写入确保数据安全，支持线程安全访问
    """

    def __init__(self, path: str | Path):
        """
        初始化存储

        Args:
            path: JSON文件路径
        """
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = self._load()
        self._lock = threading.Lock()

    def _load(self) -> dict[str, Any]:
        """从文件加载数据"""
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("存储文件损坏 %s，重新开始: %s", self._path, e)
        return {}

    def _save(self) -> None:
        """原子写入文件"""
        fd = tempfile.NamedTemporaryFile(
            mode="w",
            dir=self._path.parent,
            suffix=".tmp",
            delete=False,
        )
        try:
            json.dump(self._data, fd, indent=2, ensure_ascii=False)
            fd.close()
            Path(fd.name).replace(self._path)
        except BaseException:
            fd.close()
            Path(fd.name).unlink(missing_ok=True)
            raise

    def get(self, key: str, default: Any = None) -> Any:
        """获取值"""
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置值并持久化"""
        with self._lock:
            self._data[key] = value
            self._save()

    def delete(self, key: str) -> bool:
        """删除键"""
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._save()
                return True
            return False

    def values(self) -> dict[str, Any]:
        """获取所有数据的副本"""
        with self._lock:
            return self._data.copy()

    def keys(self) -> list[str]:
        """获取所有键"""
        with self._lock:
            return list(self._data.keys())

    def update(self, data: dict[str, Any]) -> None:
        """批量更新"""
        with self._lock:
            self._data.update(data)
            self._save()

    def clear(self) -> None:
        """清空存储"""
        with self._lock:
            self._data = {}
            self._save()

    def count(self) -> int:
        """返回存储的键数量"""
        with self._lock:
            return len(self._data)
