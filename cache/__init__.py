"""缓存管理模块。

提供代码执行缓存，对齐 DeepSeek 硬盘缓存机制：
- 本地精确结果缓存：相同代码+问题直接返回
- 消息前缀规范：构建 messages 时保持前缀一致
- 话题感知清理：话题切换时批量清理
- 上下文窗口管理：超出时丢弃最旧轮次
"""

from .semantic_cache import CacheEntry, CodeCache

__all__ = ["CacheEntry", "CodeCache"]
