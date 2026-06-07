"""缓存管理模块。

提供代码执行缓存，对齐 DeepSeek 硬盘缓存机制：
- 本地精确结果缓存：相同代码+问题直接返回
- 对话消息前缀缓存：同一工作区对话复用前缀，最大化硬盘缓存命中率
"""

from .semantic_cache import CacheEntry, CodeCache

__all__ = ["CacheEntry", "CodeCache"]
