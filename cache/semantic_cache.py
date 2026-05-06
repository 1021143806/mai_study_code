"""代码执行缓存管理模块。

设计原则（对齐 DeepSeek 硬盘缓存机制）：
- 本地精确结果缓存：相同代码+相同问题直接返回，0 token 消耗
- 消息前缀规范：构建 messages 时保持前缀一致，利用 API 端前缀缓存
- 话题感知清理：检测话题切换时批量清理旧缓存
- 上下文窗口管理：超出时丢弃最旧轮次，不调 LLM 压缩（压缩本身也烧 token）

DeepSeek 前缀缓存说明：
  API 端自动对 messages 数组做前缀匹配。只要前面部分不变，
  重复的前缀就不重复计费。我们只需保证构建 messages 时把
  不变的内容（system prompt、代码上下文）放前面，
  变化的内容（用户新问题）放最后。
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
        topic: str = "",
        ttl_seconds: int = 1800,
    ) -> None:
        self.code = code
        self.question = question
        self.result = result
        self.topic = topic
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
    2. 消息构建辅助：确保 messages 前缀一致以利用 API 缓存

    清理策略：
    - TTL 过期自动淘汰
    - LRU 容量淘汰
    - 话题切换感知清理
    - 麦麦可主动调用清理命令
    """

    def __init__(
        self,
        max_entries: int = 500,
        default_ttl_seconds: int = 1800,
        context_max_tokens: int = 8000,
    ) -> None:
        """初始化缓存。

        Args:
            max_entries: 最大缓存条目数。
            default_ttl_seconds: 默认过期时间（秒），默认 30 分钟。
            context_max_tokens: 上下文窗口最大 token 数（估算）。
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._max_entries = max_entries
        self._default_ttl = default_ttl_seconds
        self._context_max_tokens = context_max_tokens

        # 话题追踪
        self._current_topic: str = ""
        self._topic_hints: List[str] = []  # 最近的关键词，用于话题切换检测

        # 上下文窗口管理
        self._context_turns: List[Dict[str, str]] = []  # 最近的对话轮次

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
        topic: str = "",
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """写入本地缓存。

        Args:
            code: Python 代码。
            question: 用户问题。
            result: 执行结果。
            topic: 所属话题。
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
            topic=topic or self._current_topic,
            ttl_seconds=ttl_seconds,
        )

    # ================================================================
    # 消息构建辅助（利用 API 前缀缓存）
    # ================================================================

    def build_messages(
        self,
        system_prompt: str,
        code_context: str,
        user_question: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        """构建 messages 数组，保持前缀一致以利用 API 缓存。

        前缀结构（固定顺序）：
        [system] → [代码上下文] → [历史对话...] → [当前问题]

        DeepSeek 会对这个数组做前缀匹配。只要 system + 代码上下文
        不变，前面的 token 就不重复计费。

        Args:
            system_prompt: 系统提示词。
            code_context: 当前代码上下文（正在讨论的代码）。
            user_question: 用户当前问题。
            history: 历史对话轮次。

        Returns:
            List[Dict[str, str]]: messages 数组。
        """
        messages: List[Dict[str, str]] = []

        # 第1部分：system prompt（固定前缀）
        messages.append({"role": "system", "content": system_prompt})

        # 第2部分：代码上下文（固定前缀，代码不变则命中）
        if code_context:
            messages.append(
                {
                    "role": "user",
                    "content": f"当前正在讨论的代码：\n```python\n{code_context}\n```",
                }
            )

        # 第3部分：历史对话（可能变化，但最近的轮次保持稳定）
        if history:
            messages.extend(history)

        # 第4部分：当前问题（变化部分，放在最后）
        messages.append({"role": "user", "content": user_question})

        return messages

    def estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """估算 messages 的 token 数量。

        粗略估算：中文约 1.5 字符/token，英文约 4 字符/token。

        Args:
            messages: messages 数组。

        Returns:
            int: 估算的 token 数。
        """
        total_chars = sum(len(m.get("content", "")) for m in messages)
        # 保守估算：2 字符/token
        return total_chars // 2

    # ================================================================
    # 上下文窗口管理
    # ================================================================

    def add_context_turn(self, user_msg: str, assistant_msg: str) -> None:
        """添加一轮对话到上下文窗口。

        Args:
            user_msg: 用户消息。
            assistant_msg: 助手回复。
        """
        self._context_turns.append(
            {"role": "user", "content": user_msg}
        )
        self._context_turns.append(
            {"role": "assistant", "content": assistant_msg}
        )

        # 超出窗口则丢弃最旧的轮次
        self._trim_context()

    def get_context_history(self) -> List[Dict[str, str]]:
        """获取当前上下文窗口内的对话历史。

        Returns:
            List[Dict[str, str]]: 对话历史。
        """
        return list(self._context_turns)

    def _trim_context(self) -> None:
        """裁剪上下文窗口。

        当估算 token 数超出限制时，从最旧的消息开始丢弃。
        不调用 LLM 压缩（压缩本身也消耗 token）。
        """
        while (
            self._context_turns
            and self.estimate_tokens(self._context_turns) > self._context_max_tokens
        ):
            # 每次丢弃最旧的一轮（2条消息）
            if len(self._context_turns) >= 2:
                self._context_turns.pop(0)  # user
                self._context_turns.pop(0)  # assistant
            else:
                self._context_turns.pop(0)

    def reset_context(self) -> None:
        """重置上下文窗口（话题切换时调用）。"""
        self._context_turns.clear()

    # ================================================================
    # 话题感知清理
    # ================================================================

    def update_topic(self, keywords: List[str]) -> bool:
        """更新当前话题关键词，检测是否发生话题切换。

        Args:
            keywords: 当前消息的关键词列表。

        Returns:
            bool: 是否发生了话题切换。
        """
        if not self._topic_hints:
            self._topic_hints = keywords
            return False

        # 简单的话题切换检测：关键词重叠度
        old_set = set(self._topic_hints)
        new_set = set(keywords)

        if old_set and new_set:
            overlap = len(old_set & new_set) / max(len(old_set | new_set), 1)
            if overlap < 0.3:  # 重叠度低于 30%，认为话题切换
                self._on_topic_switch()
                self._topic_hints = keywords
                return True

        # 更新话题提示（保留最近的关键词）
        self._topic_hints = list(set(self._topic_hints[-10:] + keywords))
        return False

    def _on_topic_switch(self) -> None:
        """话题切换时的处理。

        清理旧话题的缓存和上下文。
        """
        # 清理旧话题的本地缓存
        if self._current_topic:
            self.invalidate_by_topic(self._current_topic)

        # 重置上下文窗口
        self.reset_context()

    def invalidate_by_topic(self, topic: str) -> int:
        """按话题清理缓存。

        Args:
            topic: 话题标识。

        Returns:
            int: 清理的条目数。
        """
        to_remove = [
            key
            for key, entry in self._cache.items()
            if entry.topic == topic
        ]
        for key in to_remove:
            del self._cache[key]
        return len(to_remove)

    # ================================================================
    # 通用缓存管理
    # ================================================================

    def invalidate_by_code(self, code_prefix: str) -> int:
        """按代码前缀清理缓存（代码被修改时调用）。

        Args:
            code_prefix: 代码前缀。

        Returns:
            int: 清理的条目数。
        """
        to_remove = [
            key
            for key, entry in self._cache.items()
            if entry.code.startswith(code_prefix)
        ]
        for key in to_remove:
            del self._cache[key]
        return len(to_remove)

    def clear(self) -> None:
        """清空所有缓存和上下文。"""
        self._cache.clear()
        self._context_turns.clear()
        self._topic_hints.clear()
        self._current_topic = ""

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
        context_tokens = self.estimate_tokens(self._context_turns)

        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
            "max_entries": self._max_entries,
            "total_hits": total_hits,
            "default_ttl_seconds": self._default_ttl,
            "context_turns": len(self._context_turns) // 2,
            "context_tokens_estimate": context_tokens,
            "context_max_tokens": self._context_max_tokens,
            "current_topic": self._current_topic,
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
