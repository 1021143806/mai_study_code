"""代码执行缓存管理模块。

设计原则：
- 本地精确结果缓存：相同代码+相同问题直接返回，0 token 消耗
- WebUI 对话缓存：管理同一工作区的消息前缀，最大化 DeepSeek 硬盘缓存命中率
"""

from typing import Any, Dict, List, Optional, Tuple

import hashlib
import time


class CacheEntry:
    """本地结果缓存条目。

    存储"相同代码+相同问题"的执行结果，
    命中时直接返回，完全不调 API。
    """

    def __init__(
        self,
        code: str,
        question: str,
        result: Any,
        ttl_seconds: int = 1800,
    ) -> None:
        self.code = code
        self.question = question
        self.result = result
        self.created_at = time.time()
        self.last_hit_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.hit_count = 0

    @property
    def is_expired(self) -> bool:
        """检查是否过期。"""
        return time.time() - self.created_at > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """获取缓存年龄（秒）。"""
        return time.time() - self.created_at

    @property
    def idle_seconds(self) -> float:
        """获取空闲时间（秒）。"""
        return time.time() - self.last_hit_at


class CodeCache:
    """代码执行缓存管理器。

    两层设计：
    1. 本地精确缓存：相同(code, question) → 直接返回结果
    2. 对话消息前缀缓存：同一工作区对话复用前缀，最大化 DeepSeek 硬盘缓存

    清理策略：
    - TTL 过期自动淘汰
    """

    def __init__(
        self,
        max_entries: int = 500,
        default_ttl_seconds: int = 1800,
    ) -> None:
        """初始化缓存。

        Args:
            max_entries: 最大缓存条目数。
            default_ttl_seconds: 默认过期时间（秒），默认 30 分钟。
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._max_entries = max_entries
        self._default_ttl = default_ttl_seconds

        # 对话消息前缀缓存：按工作区名称存储最近一次构建的消息列表
        # 用于在 WebUI 对话中复用固定前缀以利用 DeepSeek 硬盘缓存
        self._workspace_message_prefixes: Dict[str, List[Dict[str, Any]]] = {}

    # ================================================================
    # 本地精确缓存
    # ================================================================

    @staticmethod
    def make_key(code: str, question: str) -> str:
        """生成缓存键。

        基于代码内容和问题的 SHA256 哈希。
        只有代码和问题都完全相同时才命中。

        Args:
            code: Python 代码。
            question: 用户问题/指令。

        Returns:
            str: 缓存键。
        """
        content = f"CODE:{code}\nQUESTION:{question}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get(self, code: str, question: str) -> Tuple[Optional[Any], bool]:
        """查询本地精确缓存。

        Args:
            code: Python 代码。
            question: 用户问题。

        Returns:
            Tuple[Optional[Any], bool]: (缓存结果, 是否命中)。
                未命中时第一个元素为 None。
        """
        key = self.make_key(code, question)

        if key in self._cache:
            entry = self._cache[key]
            if not entry.is_expired:
                entry.last_hit_at = time.time()
                entry.hit_count += 1
                return entry.result, True
            # 过期则删除
            del self._cache[key]

        return None, False

    def set(
        self,
        code: str,
        question: str,
        result: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """写入本地缓存。

        Args:
            code: Python 代码。
            question: 用户问题。
            result: 执行结果。
            ttl_seconds: 过期时间，默认使用配置值。
        """
        if ttl_seconds is None:
            ttl_seconds = self._default_ttl

        key = self.make_key(code, question)

        # 更新已有条目
        if key in self._cache:
            self._cache[key].result = result
            self._cache[key].created_at = time.time()
            self._cache[key].ttl_seconds = ttl_seconds
            return

        # 容量控制：LRU 淘汰
        if len(self._cache) >= self._max_entries:
            self._evict_lru()

        self._cache[key] = CacheEntry(
            code=code,
            question=question,
            result=result,
            ttl_seconds=ttl_seconds,
        )

    # ================================================================
    # 对话消息前缀缓存（WebUI 对话用）
    # ================================================================

    def cache_message_prefix(
        self,
        workspace: str,
        messages: List[Dict[str, Any]],
    ) -> None:
        """缓存指定工作区的消息列表。

        存储最近一次成功构建的完整消息列表，下一轮请求中，
        如果前缀（system prompt + 工作区上下文）不变，
        可以直接复用前半部分，确保 DeepSeek 硬盘缓存命中。

        Args:
            workspace: 工作区名称。
            messages: 完整的消息列表。
        """
        self._workspace_message_prefixes[workspace] = list(messages)

    def get_message_prefix(
        self,
        workspace: str,
    ) -> List[Dict[str, Any]]:
        """获取指定工作区最近一次缓存的消息列表。

        Args:
            workspace: 工作区名称。

        Returns:
            List[Dict[str, Any]]: 缓存的消息列表，不存在时返回空列表。
        """
        return list(self._workspace_message_prefixes.get(workspace, []))

    def invalidate_workspace_prefix(self, workspace: str) -> None:
        """清除指定工作区的消息前缀缓存。

        工作区切换或配置变更时调用。

        Args:
            workspace: 工作区名称。
        """
        self._workspace_message_prefixes.pop(workspace, None)

    # ================================================================
    # 通用缓存管理
    # ================================================================

    def clear(self) -> None:
        """清空所有缓存。"""
        self._cache.clear()
        self._workspace_message_prefixes.clear()

    def clear_expired(self) -> int:
        """清理所有过期条目。

        Returns:
            int: 清理的条目数。
        """
        to_remove = [
            key for key, entry in self._cache.items() if entry.is_expired
        ]
        for key in to_remove:
            del self._cache[key]
        return len(to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息。

        Returns:
            Dict[str, Any]: 统计信息。
        """
        total = len(self._cache)
        expired = sum(1 for e in self._cache.values() if e.is_expired)
        total_hits = sum(e.hit_count for e in self._cache.values())

        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
            "max_entries": self._max_entries,
            "total_hits": total_hits,
            "default_ttl_seconds": self._default_ttl,
            "cached_workspaces": len(self._workspace_message_prefixes),
        }

    def _evict_lru(self) -> None:
        """LRU 淘汰：删除最久未使用的条目。"""
        if not self._cache:
            return
        lru_key = min(
            self._cache,
            key=lambda k: self._cache[k].last_hit_at,
        )
        del self._cache[lru_key]
